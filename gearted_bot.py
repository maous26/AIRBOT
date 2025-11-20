import os
import json
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Set, Dict

import discord
from discord.ext import commands

# ==========================
# CONFIG À ADAPTER
# ==========================

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN n'est pas défini. "
        "Configure la variable d'environnement DISCORD_BOT_TOKEN avant de lancer le bot."
    )

GUILD_ID = 1438463061181726743  # ID du serveur Gearted

# Salons
GIVEAWAY_CHANNEL_NAME = "🎁-giveaways"
HOF_CHANNEL_NAME = "🏆-hall-of-fame"
BUILDERS_ANNOUNCE_CHANNEL_NAME = "🎯-programme-builders"

# Rôles
WINNER_ROLE_NAME = "Gagnant de la semaine"
BUILDERS_ROLE_NAME = "Unité Alpha – Builders Gearted"
RECRUE_ROLE_NAME = "Recrue"
OPERATEUR_ROLE_NAME = "Opérateur"
VETERAN_ROLE_NAME = "Vétéran"

# Seuils Builders
BUILDER_THRESHOLD = 200      # seuil pour rôle Builders
VETERAN_THRESHOLD = 400      # seuil pour Vétéran

# Activité → Opérateur
OPERATOR_MIN_MESSAGES = 30   # messages min pour passer Opérateur
OPERATOR_MIN_DAYS = 7        # ancienneté min (jours) sur le serveur

COMMAND_PREFIX = "!"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PARTICIPANTS_FILE = os.path.join(BASE_DIR, "tirage_participants.json")
BUILDERS_FILE = os.path.join(BASE_DIR, "builders_points.json")
ACTIVITY_FILE = os.path.join(BASE_DIR, "activity_stats.json")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# participants[guild_id] = set(user_id)
participants: Dict[int, Set[int]] = {}

# builder_points[guild_id] = { user_id: points }
builder_points: Dict[int, Dict[int, int]] = {}

# activity_counts[guild_id] = { user_id: message_count }
activity_counts: Dict[int, Dict[int, int]] = {}


# ==========================
# PERSISTENCE JSON
# ==========================

def load_participants() -> None:
    global participants
    if not os.path.exists(PARTICIPANTS_FILE):
        participants = {}
        return
    try:
        with open(PARTICIPANTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        participants = {int(g): set(v) for g, v in data.items()}
        print(f"📂 Participants chargés : {participants}")
    except Exception as e:
        print(f"⚠️ Erreur chargement participants : {e}")
        participants = {}


def save_participants() -> None:
    try:
        data = {str(g): list(v) for g, v in participants.items()}
        with open(PARTICIPANTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 Participants sauvegardés.")
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde participants : {e}")


def load_builder_points() -> None:
    global builder_points
    if not os.path.exists(BUILDERS_FILE):
        builder_points = {}
        return
    try:
        with open(BUILDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        builder_points = {
            int(gid_str): {int(uid_str): pts for uid_str, pts in users.items()}
            for gid_str, users in data.items()
        }
        print(f"📂 Points Builders chargés : {builder_points}")
    except Exception as e:
        print(f"⚠️ Erreur chargement points Builders : {e}")
        builder_points = {}


def save_builder_points() -> None:
    try:
        data = {
            str(gid): {str(uid): pts for uid, pts in users.items()}
            for gid, users in builder_points.items()
        }
        with open(BUILDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 Points Builders sauvegardés.")
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde points Builders : {e}")


def load_activity_counts() -> None:
    global activity_counts
    if not os.path.exists(ACTIVITY_FILE):
        activity_counts = {}
        return
    try:
        with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        activity_counts = {
            int(gid_str): {int(uid_str): cnt for uid_str, cnt in users.items()}
            for gid_str, users in data.items()
        }
        print(f"📂 Stats activité chargées : {activity_counts}")
    except Exception as e:
        print(f"⚠️ Erreur chargement activité : {e}")
        activity_counts = {}


def save_activity_counts() -> None:
    try:
        data = {
            str(gid): {str(uid): cnt for uid, cnt in users.items()}
            for gid, users in activity_counts.items()
        }
        with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 Activité sauvegardée.")
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde activité : {e}")


# ==========================
# UTILITAIRES DISCORD
# ==========================

@bot.event
async def on_ready():
    print(f"✅ Connecté comme {bot.user} ({bot.user.id})")
    guild = bot.get_guild(GUILD_ID)
    if guild:
        print(f"✅ Serveur détecté : {guild.name} ({guild.id})")
    else:
        print("⚠️ Serveur non trouvé, vérifie GUILD_ID.")


def get_role(guild: discord.Guild, name: str) -> Optional[discord.Role]:
    return discord.utils.get(guild.roles, name=name)


def get_text_channel(guild: discord.Guild, name: str) -> Optional[discord.TextChannel]:
    return discord.utils.get(guild.text_channels, name=name)


def is_staff(member: discord.Member) -> bool:
    return member.guild_permissions.manage_guild


# ==========================
# EVENTS : JOIN + MESSAGE (Recrue / Opérateur auto)
# ==========================

@bot.event
async def on_member_join(member: discord.Member):
    """Donner automatiquement le rôle Recrue à tout nouveau membre."""
    if member.guild.id != GUILD_ID:
        return

    recrue_role = get_role(member.guild, RECRUE_ROLE_NAME)
    if recrue_role is None:
        print(f"⚠️ Rôle Recrue '{RECRUE_ROLE_NAME}' introuvable.")
        return

    try:
        await member.add_roles(recrue_role, reason="Nouveau membre")
        print(f"👋 Rôle Recrue donné à {member} ({member.id})")
    except discord.Forbidden:
        print("⚠️ Impossible de donner le rôle Recrue (permissions).")


async def maybe_promote_operator(member: discord.Member):
    """Promotion automatique en Opérateur si critères atteints."""
    if member.guild.id not in activity_counts:
        return

    guild_id = member.guild.id
    user_id = member.id
    msg_count = activity_counts.get(guild_id, {}).get(user_id, 0)

    # Ancienneté
    if member.joined_at is None:
        return

    now = datetime.now(timezone.utc)
    if now - member.joined_at < timedelta(days=OPERATOR_MIN_DAYS):
        return

    if msg_count < OPERATOR_MIN_MESSAGES:
        return

    oper_role = get_role(member.guild, OPERATEUR_ROLE_NAME)
    if oper_role is None:
        print(f"⚠️ Rôle Opérateur '{OPERATEUR_ROLE_NAME}' introuvable.")
        return

    if oper_role in member.roles:
        return

    try:
        await member.add_roles(oper_role, reason="Critères d'activité atteints (messages + ancienneté)")
        print(f"📈 {member} promu automatiquement en Opérateur.")
    except discord.Forbidden:
        print("⚠️ Impossible de donner le rôle Opérateur (permissions).")


@bot.event
async def on_message(message: discord.Message):
    """Compter les messages pour la promotion Opérateur + laisser passer les commandes."""
    if message.author.bot:
        await bot.process_commands(message)
        return

    if message.guild and message.guild.id == GUILD_ID:
        guild_id = message.guild.id
        user_id = message.author.id

        if guild_id not in activity_counts:
            activity_counts[guild_id] = {}

        activity_counts[guild_id][user_id] = activity_counts[guild_id].get(user_id, 0) + 1
        save_activity_counts()

        # Essayer de promouvoir en Opérateur
        if isinstance(message.author, discord.Member):
            await maybe_promote_operator(message.author)

    await bot.process_commands(message)


# ==========================
# COMMANDES DE SANTÉ
# ==========================

@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.send("🏓 Pong, Gearted bot opérationnel.")


# ==========================
# SYSTÈME DE TIRAGE
# ==========================

@bot.command(name="tirage")
async def tirage(ctx: commands.Context, action: Optional[str] = None):
    """
    Usage :
    - Membres : `!tirage` dans #🎁-giveaways  → inscription
    - Staff  : `!tirage go`      → tirage
               `!tirage liste`   → voir inscrits
               `!tirage reset`   → vider la liste
    """

    guild = ctx.guild
    if guild is None or guild.id != GUILD_ID:
        await ctx.send("⚠️ Cette commande doit être utilisée sur le serveur Gearted.")
        return

    giveaway_channel = get_text_channel(guild, GIVEAWAY_CHANNEL_NAME)

    # Participation
    if action is None:
        if giveaway_channel and ctx.channel.id != giveaway_channel.id:
            await ctx.send(
                f"⚠️ Pour participer au tirage, utilise cette commande dans {giveaway_channel.mention}."
            )
            return

        if guild.id not in participants:
            participants[guild.id] = set()

        user_id = ctx.author.id
        if user_id in participants[guild.id]:
            await ctx.send(f"✅ {ctx.author.mention}, tu es **déjà inscrit** pour le tirage de cette semaine.")
        else:
            participants[guild.id].add(user_id)
            save_participants()
            await ctx.send(
                f"🎯 Participation enregistrée pour {ctx.author.mention}.\n"
                f"Tu feras partie du prochain tirage de la semaine."
            )
        return

    # Staff only
    action = action.lower()

    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("⛔ Seul le staff peut utiliser `!tirage {go|liste|reset}`.")
        return

    guild_participants = list(participants.get(guild.id, set()))

    if action == "liste":
        if not guild_participants:
            await ctx.send("📋 Aucun participant inscrit pour le moment.")
            return

        members = [
            m for uid in guild_participants
            if (m := guild.get_member(uid)) is not None and not m.bot
        ]

        if not members:
            await ctx.send("📋 Aucun participant valide trouvé (membres introuvables ou bots).")
            return

        max_display = 30
        display_members = ", ".join(m.mention for m in members[:max_display])
        extra = ""
        if len(members) > max_display:
            extra = f"\n… et **{len(members) - max_display}** autres."

        await ctx.send(
            f"📋 **Participants inscrits au tirage ({len(members)}) :**\n"
            f"{display_members}{extra}"
        )
        return

    if action == "reset":
        participants[guild.id] = set()
        save_participants()
        await ctx.send("🧹 La liste des participants au tirage a été **réinitialisée** pour ce serveur.")
        return

    if action in ("go", "start", "pick"):
        if not guild_participants:
            await ctx.send("❌ Aucun participant inscrit pour ce tirage (personne n'a tapé `!tirage`).")
            return

        members = [
            m for uid in guild_participants
            if (m := guild.get_member(uid)) is not None and not m.bot
        ]

        if not members:
            await ctx.send("❌ Aucun participant valide trouvé (membres introuvables ou bots uniquement).")
            return

        winner: discord.Member = random.choice(members)

        winner_role = get_role(guild, WINNER_ROLE_NAME)
        if winner_role is None:
            await ctx.send(
                f"⚠️ Rôle `{WINNER_ROLE_NAME}` introuvable. "
                f"Le gagnant sera annoncé mais ne recevra pas de rôle."
            )
        else:
            for m in winner_role.members:
                if m.id != winner.id:
                    try:
                        await m.remove_roles(winner_role, reason="Nouveau gagnant de la semaine")
                    except discord.Forbidden:
                        pass
            try:
                await winner.add_roles(winner_role, reason="Gagnant tirage de la semaine")
            except discord.Forbidden:
                await ctx.send("⚠️ Impossible de donner le rôle au gagnant (permissions insuffisantes).")

        await ctx.send(
            f"🎉 **Gagnant tiré au sort : {winner.mention}**\n"
            f"Participants inscrits : **{len(members)}**\n\n"
            f"ℹ️ Si le gagnant n'a pas vraiment rempli les conditions du challenge,\n"
            f"tu peux relancer un tirage avec `!tirage go`."
        )

        hof_channel = get_text_channel(guild, HOF_CHANNEL_NAME)
        if hof_channel:
            embed = discord.Embed(
                title="🏆 Gagnant du tirage de la semaine",
                description=(
                    f"Gagnant : {winner.mention}\n"
                    f"Nombre de participants : **{len(members)}**"
                ),
                color=0xFFD700,
            )
            embed.set_footer(text="Gearted • Missions & Récompenses")
            await hof_channel.send(embed=embed)
        else:
            await ctx.send(f"⚠️ Salon hall of fame introuvable : `{HOF_CHANNEL_NAME}`")

        return

    await ctx.send(
        "⚠️ Usage de la commande `!tirage` :\n"
        "• Membres : `!tirage` dans #🎁-giveaways pour s'inscrire\n"
        "• Staff  : `!tirage liste` pour voir les inscrits\n"
        "          `!tirage go` pour lancer le tirage\n"
        "          `!tirage reset` pour vider la liste"
    )


# ==========================
# SYSTÈME DE POINTS BUILDERS & PROMOS BUILDERS / VÉTÉRAN
# ==========================

def get_user_builder_points(guild_id: int, user_id: int) -> int:
    return builder_points.get(guild_id, {}).get(user_id, 0)


def set_user_builder_points(guild_id: int, user_id: int, points: int) -> None:
    if guild_id not in builder_points:
        builder_points[guild_id] = {}
    builder_points[guild_id][user_id] = max(0, points)


async def maybe_grant_builder_and_veteran(guild: discord.Guild, member: discord.Member):
    """Attribue automatiquement Builders et Vétéran en fonction des points."""
    points = get_user_builder_points(guild.id, member.id)

    builders_role = get_role(guild, BUILDERS_ROLE_NAME)
    veteran_role = get_role(guild, VETERAN_ROLE_NAME)

    announce_channel = (
        get_text_channel(guild, BUILDERS_ANNOUNCE_CHANNEL_NAME)
        or get_text_channel(guild, HOF_CHANNEL_NAME)
    )

    # Builders
    if builders_role is not None and points >= BUILDER_THRESHOLD and builders_role not in member.roles:
        try:
            await member.add_roles(builders_role, reason="Seuil de points Builders atteint")
            msg = (
                f"🛠️ **Nouveau Builder Gearted !**\n"
                f"{member.mention} vient d'atteindre **{points} points Builders** "
                f"et débloque le rôle **{builders_role.mention}** 🎖️"
            )
            if announce_channel:
                await announce_channel.send(msg)
        except discord.Forbidden:
            print("⚠️ Impossible d'ajouter le rôle Builders (permissions).")

    # Vétéran
    if veteran_role is not None and points >= VETERAN_THRESHOLD and veteran_role not in member.roles:
        try:
            await member.add_roles(veteran_role, reason="Seuil de points Vétéran atteint")
            msg = (
                f"🏅 **Nouveau Vétéran Gearted !**\n"
                f"{member.mention} vient d'atteindre **{points} points Builders** "
                f"et débloque le rôle **{veteran_role.mention}** 🔥"
            )
            if announce_channel:
                await announce_channel.send(msg)
        except discord.Forbidden:
            print("⚠️ Impossible d'ajouter le rôle Vétéran (permissions).")


@bot.command(name="builderadd")
async def builder_add(ctx: commands.Context, member: discord.Member, points: int):
    """Staff : ajouter des points Builders à un membre."""
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("⛔ Seul le staff peut utiliser cette commande.")
        return

    if points <= 0:
        await ctx.send("⚠️ Le nombre de points doit être positif.")
        return

    guild = ctx.guild
    if guild is None:
        return

    current = get_user_builder_points(guild.id, member.id)
    new_points = current + points
    set_user_builder_points(guild.id, member.id, new_points)
    save_builder_points()

    await ctx.send(
        f"🧱 {member.mention} gagne **+{points} points Builders** "
        f"(total : **{new_points}**)."
    )

    await maybe_grant_builder_and_veteran(guild, member)


@bot.command(name="builderremove")
async def builder_remove(ctx: commands.Context, member: discord.Member, points: int):
    """Staff : retirer des points Builders à un membre."""
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("⛔ Seul le staff peut utiliser cette commande.")
        return

    if points <= 0:
        await ctx.send("⚠️ Le nombre de points doit être positif.")
        return

    guild = ctx.guild
    if guild is None:
        return

    current = get_user_builder_points(guild.id, member.id)
    new_points = max(0, current - points)
    set_user_builder_points(guild.id, member.id, new_points)
    save_builder_points()

    await ctx.send(
        f"📉 {member.mention} perd **-{points} points Builders** "
        f"(total : **{new_points}**)."
    )


@bot.command(name="builderstats")
async def builder_stats(ctx: commands.Context, member: Optional[discord.Member] = None):
    """Voir les points Builders."""
    guild = ctx.guild
    if guild is None:
        return

    target = member or ctx.author

    if member is not None and (not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author)):
        await ctx.send("⛔ Seul le staff peut voir les points des autres membres.")
        return

    pts = get_user_builder_points(guild.id, target.id)
    await ctx.send(
        f"🧱 Points Builders de {target.mention} : **{pts}** "
        f"(Builders : {BUILDER_THRESHOLD} pts • Vétéran : {VETERAN_THRESHOLD} pts)"
    )


@bot.command(name="builderboard")
async def builder_board(ctx: commands.Context, limit: int = 10):
    """Afficher le classement Builders."""
    guild = ctx.guild
    if guild is None:
        return

    users_pts = builder_points.get(guild.id, {})
    if not users_pts:
        await ctx.send("📊 Aucun point Builders enregistré pour l'instant.")
        return

    sorted_users = sorted(users_pts.items(), key=lambda kv: kv[1], reverse=True)
    lines = []
    rank = 1
    for user_id, pts in sorted_users[: max(1, min(limit, 25))]:
        member = guild.get_member(user_id)
        if member is None or member.bot:
            continue
        lines.append(f"**#{rank}** — {member.mention} : **{pts}** pts")
        rank += 1

    if not lines:
        await ctx.send("📊 Aucun membre valide avec des points Builders.")
        return

    desc = "\n".join(lines)
    embed = discord.Embed(
        title="🏗️ Classement Builders Gearted",
        description=desc,
        color=0x3BA55D,
    )
    embed.set_footer(text=f"Seuil Builders : {BUILDER_THRESHOLD} pts • Vétéran : {VETERAN_THRESHOLD} pts")
    await ctx.send(embed=embed)


# ==========================
# MAIN
# ==========================

if __name__ == "__main__":
    load_participants()
    load_builder_points()
    load_activity_counts()
    bot.run(BOT_TOKEN)

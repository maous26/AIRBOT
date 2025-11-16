import os
import json
import random
from typing import Optional, Set, Dict

import discord
from discord.ext import commands

# ==========================
# CONFIG À ADAPTER
# ==========================

# ⚠️ Mets ton token de bot dans une variable d'environnement de préférence :
# export DISCORD_BOT_TOKEN="ton-token"
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "TON_BOT_TOKEN_ICI")

GUILD_ID = 1434470610565726325  # <-- ID de ton serveur Gearted

GIVEAWAY_CHANNEL_NAME = "🎁-giveaways"        # salon où les gens tapent !tirage
HOF_CHANNEL_NAME = "🏆-hall-of-fame"          # salon d'annonce des gagnants du tirage
WINNER_ROLE_NAME = "Gagnant de la semaine"    # rôle gagnant tirage

# --- Système Builders ---
BUILDERS_ROLE_NAME = "Unité Alpha – Builders Gearted"  # adapte au nom EXACT du rôle
BUILDERS_ANNOUNCE_CHANNEL_NAME = "🎯-programme-builders"  # salon QG Builders
BUILDER_THRESHOLD = 200  # seuil de points pour débloquer le rôle Builders

COMMAND_PREFIX = "!"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Fichier JSON pour la persistance des participants tirage
PARTICIPANTS_FILE = os.path.join(BASE_DIR, "tirage_participants.json")

# Fichier JSON pour la persistance des points Builders
BUILDERS_FILE = os.path.join(BASE_DIR, "builders_points.json")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# participants[guild_id] = set(user_id)
participants: Dict[int, Set[int]] = {}

# builder_points[guild_id] = { user_id: points }
builder_points: Dict[int, Dict[int, int]] = {}


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
        participants = {
            int(gid_str): set(user_ids)
            for gid_str, user_ids in data.items()
        }
        print(f"📂 Participants chargés : {participants}")
    except Exception as e:
        print(f"⚠️ Erreur chargement participants : {e}")
        participants = {}


def save_participants() -> None:
    try:
        data = {str(gid): list(user_ids) for gid, user_ids in participants.items()}
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
    # Staff = permission "Gérer le serveur"
    return member.guild_permissions.manage_guild


# ==========================
# COMMANDES DE DEBUG / SANTÉ
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
    - Membres : `!tirage` dans #🎁-giveaways  → inscription à la liste
    - Staff  : `!tirage go`      → tirage parmi les inscrits
               `!tirage liste`   → voir la liste des inscrits
               `!tirage reset`   → vider la liste
    """

    guild = ctx.guild
    if guild is None or guild.id != GUILD_ID:
        await ctx.send("⚠️ Cette commande doit être utilisée sur le serveur Gearted.")
        return

    giveaway_channel = get_text_channel(guild, GIVEAWAY_CHANNEL_NAME)

    # --- CAS 1 : participation membre ---
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

    # à partir d'ici : staff only
    action = action.lower()

    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("⛔ Seul le staff peut utiliser `!tirage {go|liste|reset}`.")
        return

    guild_participants = list(participants.get(guild.id, set()))

    # --- CAS 2 : !tirage liste ---
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

    # --- CAS 3 : !tirage reset ---
    if action == "reset":
        participants[guild.id] = set()
        save_participants()
        await ctx.send("🧹 La liste des participants au tirage a été **réinitialisée** pour ce serveur.")
        return

    # --- CAS 4 : !tirage go / start / pick ---
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

    # --- CAS 5 : argument inconnu ---
    await ctx.send(
        "⚠️ Usage de la commande `!tirage` :\n"
        "• Membres : `!tirage` dans #🎁-giveaways pour s'inscrire\n"
        "• Staff  : `!tirage liste` pour voir les inscrits\n"
        "          `!tirage go` pour lancer le tirage\n"
        "          `!tirage reset` pour vider la liste"
    )


@tirage.error
async def tirage_error(ctx: commands.Context, error):
    print(f"[ERREUR COMMANDE !tirage] {error}")


# ==========================
# SYSTÈME DE POINTS BUILDERS
# ==========================

def get_user_builder_points(guild_id: int, user_id: int) -> int:
    return builder_points.get(guild_id, {}).get(user_id, 0)


def set_user_builder_points(guild_id: int, user_id: int, points: int) -> None:
    if guild_id not in builder_points:
        builder_points[guild_id] = {}
    builder_points[guild_id][user_id] = max(0, points)


async def maybe_grant_builder_role(guild: discord.Guild, member: discord.Member):
    """Donne le rôle Builders si le seuil est atteint."""
    points = get_user_builder_points(guild.id, member.id)
    builders_role = get_role(guild, BUILDERS_ROLE_NAME)
    if builders_role is None:
        print(f"⚠️ Rôle Builders `{BUILDERS_ROLE_NAME}` introuvable.")
        return

    if points >= BUILDER_THRESHOLD and builders_role not in member.roles:
        try:
            await member.add_roles(builders_role, reason="Seuil de points Builders atteint")
        except discord.Forbidden:
            print("⚠️ Impossible d'ajouter le rôle Builders (permissions).")
            return

        announce_channel = get_text_channel(guild, BUILDERS_ANNOUNCE_CHANNEL_NAME) or \
                           get_text_channel(guild, HOF_CHANNEL_NAME)

        msg = (
            f"🛠️ **Nouveau Builder Gearted !**\n"
            f"{member.mention} vient d'atteindre **{points} points Builders** "
            f"et débloque le rôle **{builders_role.mention}** 🎖️"
        )
        if announce_channel:
            await announce_channel.send(msg)
        else:
            print("⚠️ Aucun salon d'annonce Builders trouvé.")


@bot.command(name="builderadd")
async def builder_add(ctx: commands.Context, member: discord.Member, points: int):
    """Staff : ajouter des points Builders à un membre.
    Usage: !builderadd @user 10
    """
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

    await maybe_grant_builder_role(guild, member)


@bot.command(name="builderremove")
async def builder_remove(ctx: commands.Context, member: discord.Member, points: int):
    """Staff : retirer des points Builders à un membre.
    Usage: !builderremove @user 5
    """
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
    """Voir les points Builders.
    Usage:
      - !builderstats           → voir ses propres points
      - !builderstats @user     → staff : voir ceux de quelqu'un
    """
    guild = ctx.guild
    if guild is None:
        return

    target = member or ctx.author

    # Si on demande les points de quelqu'un d'autre, nécessiter staff
    if member is not None and (not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author)):
        await ctx.send("⛔ Seul le staff peut voir les points des autres membres.")
        return

    pts = get_user_builder_points(guild.id, target.id)
    await ctx.send(
        f"🧱 Points Builders de {target.mention} : **{pts}** "
        f"(seuil rôle Builders : **{BUILDER_THRESHOLD}**)"
    )


@bot.command(name="builderboard")
async def builder_board(ctx: commands.Context, limit: int = 10):
    """Afficher le classement Builders.
    Usage: !builderboard [limit]
    """
    guild = ctx.guild
    if guild is None:
        return

    users_pts = builder_points.get(guild.id, {})
    if not users_pts:
        await ctx.send("📊 Aucun point Builders enregistré pour l'instant.")
        return

    # Trier par points décroissants
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
    embed.set_footer(text=f"Seuil pour le rôle Builders : {BUILDER_THRESHOLD} points")
    await ctx.send(embed=embed)


@builder_add.error
@builder_remove.error
@builder_stats.error
@builder_board.error
async def builder_cmd_error(ctx: commands.Context, error):
    print(f"[ERREUR COMMANDE BUILDERS] {error}")
    # Tu peux afficher un message si tu veux :
    # await ctx.send(f"⚠️ Erreur commande Builders : {error}")


# ==========================
# MAIN
# ==========================

if __name__ == "__main__":
    load_participants()
    load_builder_points()
    bot.run(BOT_TOKEN)

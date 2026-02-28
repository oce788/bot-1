#!/usr/bin/env python3
"""
🎫 Bot Discord de Gestion de Tickets
Utilise discord.py avec commandes slash, autocomplete et boutons d'action.

Installation :
    pip install discord.py python-dotenv

Lancement :
    python ticket_bot.py
"""

import json
import os
import uuid
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
ROLE_AIDE  = os.environ.get("ROLE_AIDE", "Aide")

if not BOT_TOKEN:
    raise ValueError(f"BOT_TOKEN manquant. Variables dispo: {list(os.environ.keys())}")
if not CHANNEL_ID:
    raise ValueError(f"CHANNEL_ID manquant. Variables dispo: {list(os.environ.keys())}")

TICKETS_FILE = "tickets.json"

PRIORITY_COLORS = {
    1: discord.Color.red(),
    2: discord.Color.orange(),
    3: discord.Color.yellow(),
    4: discord.Color.green(),
}
PRIORITY_LABELS = {
    1: "🔴 Critique",
    2: "🟠 Haute",
    3: "🟡 Moyenne",
    4: "🟢 Basse",
}
STATUS_LABELS = {
    "ouvert":     "🔓 Ouvert",
    "en_cours":   "🔄 En cours",
    "en_attente": "⏳ En attente",
    "résolu":     "✅ Résolu",
    "fermé":      "🔒 Fermé",
}

def load_tickets() -> dict:
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tickets(tickets: dict):
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)

def short_id(full_id: str) -> str:
    return full_id[:8].upper()

def build_embed(t: dict) -> discord.Embed:
    color = PRIORITY_COLORS.get(t["priority"], discord.Color.blurple())
    embed = discord.Embed(
        title=f"🎫 Ticket #{short_id(t['id'])} — {t['title']}",
        description=t.get("description") or "*Aucune description*",
        color=color,
        timestamp=datetime.fromisoformat(t["created_at"]),
    )
    embed.add_field(name="Statut",    value=STATUS_LABELS.get(t["status"], t["status"]), inline=True)
    embed.add_field(name="Priorité",  value=PRIORITY_LABELS.get(t["priority"], "?"),     inline=True)
    embed.add_field(name="Assigné à", value=t.get("assignee") or "*Non assigné*",        inline=True)
    if t.get("comments"):
        last = t["comments"][-1]
        embed.add_field(
            name=f"💬 Dernier commentaire ({last['author']})",
            value=last["text"][:200],
            inline=False,
        )
    embed.set_footer(text=f"ID : {t['id']}")
    return embed

class TicketActionsView(discord.ui.View):
    def __init__(self, ticket_id: str):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id

    def _get_ticket(self):
        tickets = load_tickets()
        return tickets, tickets.get(self.ticket_id)

    def _is_aide(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        return any(r.name == ROLE_AIDE for r in interaction.user.roles)

    async def _check(self, interaction: discord.Interaction) -> bool:
        if not self._is_aide(interaction):
            await interaction.response.send_message(
                f"❌ Le rôle **{ROLE_AIDE}** est requis.", ephemeral=True
            )
            return False
        return True

    async def _change_status(self, interaction: discord.Interaction, new_status: str):
        if not await self._check(interaction):
            return
        tickets, t = self._get_ticket()
        if not t:
            await interaction.response.send_message("❌ Ticket introuvable.", ephemeral=True)
            return
        if new_status == "fermé":
            embed = discord.Embed(
                title=f"🔒 Ticket #{short_id(t['id'])} fermé et supprimé",
                description=f"**{t['title']}** fermé par {interaction.user.mention}.",
                color=discord.Color.red(),
            )
            embed.add_field(name="Assigné à", value=t.get("assignee") or "*Non assigné*", inline=True)
            embed.add_field(name="Priorité",  value=PRIORITY_LABELS.get(t["priority"], "?"), inline=True)
            del tickets[self.ticket_id]
            save_tickets(tickets)
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            return
        t["status"] = new_status
        t["updated_at"] = datetime.now().isoformat()
        save_tickets(tickets)
        embed = build_embed(t)
        embed.set_footer(text=f"Statut modifié par {interaction.user} → {STATUS_LABELS[new_status]}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔄 En cours",   style=discord.ButtonStyle.primary)
    async def btn_en_cours(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._change_status(interaction, "en_cours")

    @discord.ui.button(label="⏳ En attente", style=discord.ButtonStyle.secondary)
    async def btn_en_attente(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._change_status(interaction, "en_attente")

    @discord.ui.button(label="✅ Résolu",     style=discord.ButtonStyle.success)
    async def btn_resolu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._change_status(interaction, "résolu")

    @discord.ui.button(label="🔒 Fermer",     style=discord.ButtonStyle.danger)
    async def btn_fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._change_status(interaction, "fermé")

    @discord.ui.button(label="🗑️ Supprimer",  style=discord.ButtonStyle.danger)
    async def btn_supprimer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        tickets, t = self._get_ticket()
        if not t:
            await interaction.response.send_message("❌ Ticket introuvable.", ephemeral=True)
            return
        del tickets[self.ticket_id]
        save_tickets(tickets)
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            title=f"🗑️ Ticket #{short_id(t['id'])} supprimé",
            description=f"**{t['title']}** supprimé par {interaction.user.mention}.",
            color=discord.Color.dark_red(),
        )
        await interaction.response.edit_message(embed=embed, view=self)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

def check_channel(interaction: discord.Interaction) -> bool:
    return interaction.channel_id == CHANNEL_ID

def has_role_aide(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    return any(r.name == ROLE_AIDE for r in interaction.user.roles)

async def deny_permission(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"❌ Vous n'avez pas la permission. Le rôle **{ROLE_AIDE}** est requis.",
        ephemeral=True
    )

async def autocomplete_ticket_id(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    tickets = load_tickets()
    choices = []
    for tid, t in tickets.items():
        sid = short_id(tid)
        label = f"#{sid} — {t['title'][:35]} [{STATUS_LABELS.get(t['status'], t['status'])}]"
        if current.upper() in sid or current.lower() in t["title"].lower():
            choices.append(app_commands.Choice(name=label, value=sid))
        if len(choices) >= 25:
            break
    return choices

@bot.event
async def on_ready():
    await tree.sync()
    channel = bot.get_channel(CHANNEL_ID)
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    print(f"📡 Salon cible : #{channel.name if channel else 'introuvable'}")
    if channel:
        await channel.send(
            embed=discord.Embed(
                title="🎫 Bot de tickets en ligne !",
                description="Utilisez `/tickets creer` pour ouvrir un ticket.",
                color=discord.Color.blurple(),
            )
        )

tickets_group = app_commands.Group(name="tickets", description="🎫 Gestion des tickets")

@tickets_group.command(name="creer", description="Créer un nouveau ticket")
@app_commands.describe(titre="Titre du ticket", description="Description détaillée", assignee="Personne assignée", priorite="1=Critique 2=Haute 3=Moyenne 4=Basse")
async def tickets_creer(interaction: discord.Interaction, titre: str, description: str = "", assignee: str = "", priorite: int = 3):
    if not check_channel(interaction):
        await interaction.response.send_message("❌ Utilisez cette commande dans le salon dédié.", ephemeral=True)
        return
    if priorite not in PRIORITY_LABELS:
        priorite = 3
    all_tickets = load_tickets()
    ticket_id = str(uuid.uuid4())
    all_tickets[ticket_id] = {
        "id": ticket_id, "title": titre, "description": description,
        "assignee": assignee or None, "priority": priorite, "status": "ouvert",
        "created_at": datetime.now().isoformat(), "updated_at": None,
        "comments": [], "author": str(interaction.user),
    }
    save_tickets(all_tickets)
    embed = build_embed(all_tickets[ticket_id])
    embed.set_author(name=f"Créé par {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message("✅ Ticket créé !", embed=embed, view=TicketActionsView(ticket_id))

@tickets_group.command(name="liste", description="Lister les tickets (filtre optionnel par statut)")
@app_commands.describe(statut="Filtrer : ouvert | en_cours | en_attente | résolu | fermé")
async def tickets_liste(interaction: discord.Interaction, statut: str = ""):
    if not check_channel(interaction):
        await interaction.response.send_message("❌ Mauvais salon.", ephemeral=True); return
    if not has_role_aide(interaction):
        await deny_permission(interaction); return
    all_tickets = load_tickets()
    results = list(all_tickets.values())
    if statut:
        results = [t for t in results if t["status"] == statut.lower()]
    results.sort(key=lambda x: (x["priority"], x["created_at"]))
    if not results:
        await interaction.response.send_message("📭 Aucun ticket trouvé.", ephemeral=True); return
    lines = [
        f"`#{short_id(t['id'])}` {PRIORITY_LABELS[t['priority']]}  {STATUS_LABELS.get(t['status'], t['status'])}  **{t['title']}**"
        + (f" — *{t['assignee']}*" if t.get("assignee") else "") for t in results
    ]
    embed = discord.Embed(title=f"📋 Tickets ({len(results)})" + (f" — {statut}" if statut else ""), description="\n".join(lines), color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed)

@tickets_group.command(name="voir", description="Afficher le détail d'un ticket")
@app_commands.describe(ticket_id="Sélectionnez un ticket")
@app_commands.autocomplete(ticket_id=autocomplete_ticket_id)
async def tickets_voir(interaction: discord.Interaction, ticket_id: str):
    if not check_channel(interaction):
        await interaction.response.send_message("❌ Mauvais salon.", ephemeral=True); return
    if not has_role_aide(interaction):
        await deny_permission(interaction); return
    all_tickets = load_tickets()
    matches = [t for tid, t in all_tickets.items() if short_id(tid) == ticket_id.upper() or tid.upper().startswith(ticket_id.upper())]
    if not matches:
        await interaction.response.send_message(f"❌ Ticket `{ticket_id}` introuvable.", ephemeral=True); return
    t = matches[0]
    embed = build_embed(t)
    if t.get("comments"):
        comments_text = "\n".join(f"[{c['date'][:16]}] **{c['author']}** : {c['text']}" for c in t["comments"])
        embed.add_field(name=f"💬 Commentaires ({len(t['comments'])})", value=comments_text[:1000], inline=False)
    await interaction.response.send_message(embed=embed, view=TicketActionsView(t["id"]))

@tickets_group.command(name="statut", description="Changer le statut d'un ticket")
@app_commands.describe(ticket_id="Sélectionnez un ticket", statut="ouvert | en_cours | en_attente | résolu | fermé")
@app_commands.autocomplete(ticket_id=autocomplete_ticket_id)
async def tickets_statut(interaction: discord.Interaction, ticket_id: str, statut: str):
    if not check_channel(interaction):
        await interaction.response.send_message("❌ Mauvais salon.", ephemeral=True); return
    if not has_role_aide(interaction):
        await deny_permission(interaction); return
    if statut not in STATUS_LABELS:
        await interaction.response.send_message(f"❌ Statut invalide. Valeurs : {', '.join(STATUS_LABELS.keys())}", ephemeral=True); return
    all_tickets = load_tickets()
    matches = [tid for tid in all_tickets if short_id(tid) == ticket_id.upper() or tid.upper().startswith(ticket_id.upper())]
    if not matches:
        await interaction.response.send_message(f"❌ Ticket `{ticket_id}` introuvable.", ephemeral=True); return
    t = all_tickets[matches[0]]
    old_status = t["status"]
    t["status"] = statut
    t["updated_at"] = datetime.now().isoformat()
    if statut == "fermé":
        embed = discord.Embed(title=f"🔒 Ticket #{short_id(t['id'])} fermé", description=f"**{t['title']}** fermé par {interaction.user.mention}.", color=discord.Color.red())
        del all_tickets[matches[0]]
        save_tickets(all_tickets)
        await interaction.response.send_message(embed=embed); return
    save_tickets(all_tickets)
    embed = build_embed(t)
    embed.set_footer(text=f"Modifié par {interaction.user} : {STATUS_LABELS[old_status]} → {STATUS_LABELS[statut]}")
    await interaction.response.send_message("✅ Statut mis à jour !", embed=embed, view=TicketActionsView(t["id"]))

@tickets_group.command(name="commenter", description="Ajouter un commentaire à un ticket")
@app_commands.describe(ticket_id="Sélectionnez un ticket", commentaire="Votre commentaire")
@app_commands.autocomplete(ticket_id=autocomplete_ticket_id)
async def tickets_commenter(interaction: discord.Interaction, ticket_id: str, commentaire: str):
    if not check_channel(interaction):
        await interaction.response.send_message("❌ Mauvais salon.", ephemeral=True); return
    if not has_role_aide(interaction):
        await deny_permission(interaction); return
    all_tickets = load_tickets()
    matches = [tid for tid in all_tickets if short_id(tid) == ticket_id.upper() or tid.upper().startswith(ticket_id.upper())]
    if not matches:
        await interaction.response.send_message(f"❌ Ticket `{ticket_id}` introuvable.", ephemeral=True); return
    t = all_tickets[matches[0]]
    t["comments"].append({"author": str(interaction.user.display_name), "text": commentaire, "date": datetime.now().isoformat()})
    t["updated_at"] = datetime.now().isoformat()
    save_tickets(all_tickets)
    embed = build_embed(t)
    await interaction.response.send_message(f"💬 Commentaire ajouté au ticket `#{short_id(t['id'])}`", embed=embed, view=TicketActionsView(t["id"]))

@tickets_group.command(name="supprimer", description="Supprimer un ticket")
@app_commands.describe(ticket_id="Sélectionnez un ticket")
@app_commands.autocomplete(ticket_id=autocomplete_ticket_id)
async def tickets_supprimer(interaction: discord.Interaction, ticket_id: str):
    if not check_channel(interaction):
        await interaction.response.send_message("❌ Mauvais salon.", ephemeral=True); return
    if not has_role_aide(interaction):
        await deny_permission(interaction); return
    all_tickets = load_tickets()
    matches = [tid for tid in all_tickets if short_id(tid) == ticket_id.upper() or tid.upper().startswith(ticket_id.upper())]
    if not matches:
        await interaction.response.send_message(f"❌ Ticket `{ticket_id}` introuvable.", ephemeral=True); return
    t = all_tickets.pop(matches[0])
    save_tickets(all_tickets)
    await interaction.response.send_message(f"🗑️ Ticket `#{short_id(t['id'])}` — **{t['title']}** supprimé par {interaction.user.mention}.")

@tickets_group.command(name="stats", description="Afficher les statistiques des tickets")
async def tickets_stats(interaction: discord.Interaction):
    if not check_channel(interaction):
        await interaction.response.send_message("❌ Mauvais salon.", ephemeral=True); return
    if not has_role_aide(interaction):
        await deny_permission(interaction); return
    all_tickets = load_tickets()
    total = len(all_tickets)
    by_status = {k: 0 for k in STATUS_LABELS}
    by_prio   = {k: 0 for k in PRIORITY_LABELS}
    for t in all_tickets.values():
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        by_prio[t["priority"]] = by_prio.get(t["priority"], 0) + 1
    embed = discord.Embed(title="📊 Statistiques des tickets", color=discord.Color.blurple())
    embed.add_field(name="Total", value=str(total), inline=False)
    embed.add_field(name="Par statut",   value="\n".join(f"{v} : **{by_status.get(k, 0)}**" for k, v in STATUS_LABELS.items()), inline=True)
    embed.add_field(name="Par priorité", value="\n".join(f"{v} : **{by_prio.get(k, 0)}**"   for k, v in PRIORITY_LABELS.items()), inline=True)
    await interaction.response.send_message(embed=embed)

tree.add_command(tickets_group)

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

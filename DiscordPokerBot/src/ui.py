import discord
from discord.ui import View, button

class InteractionContext:
    """Shim to make a discord.Interaction look like a commands.Context for our commands."""
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.author = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild

    async def send(self, *args, **kwargs):
        # forward to channel instead of ephemeral
        return await self.channel.send(*args, **kwargs)


class ActionView(View):
    def __init__(self, bot, table, ctx):
        super().__init__(timeout=None)
        self.bot = bot
        self.table = table
        self.ctx = ctx  # kept for channel reference

    async def _check_turn(self, interaction: discord.Interaction):
        """Ensure only the current player can act."""
        current = self.table.players[self.table.turn_idx]
        if interaction.user.id != current.user_id:
            await interaction.response.send_message("Not your turn!", ephemeral=True)
            return False
        # disable old buttons immediately so they can't be spammed
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        return True

    # ---- Buttons ----
    @button(label="Check", style=discord.ButtonStyle.secondary)
    async def check_btn(self, interaction: discord.Interaction, _):
        if not await self._check_turn(interaction): return
        ctx = InteractionContext(interaction)
        await self.bot.get_command("check").callback(ctx)

    @button(label="Call", style=discord.ButtonStyle.primary)
    async def call_btn(self, interaction: discord.Interaction, _):
        if not await self._check_turn(interaction): return
        ctx = InteractionContext(interaction)
        await self.bot.get_command("call").callback(ctx)

    @button(label="1/3 Pot", style=discord.ButtonStyle.success)
    async def pot_third_btn(self, interaction: discord.Interaction, _):
        if not await self._check_turn(interaction): return
        amt = max(1, self.table.pot // 3)
        ctx = InteractionContext(interaction)
        await self.bot.get_command("raise").callback(ctx, amt)

    @button(label="1/2 Pot", style=discord.ButtonStyle.success)
    async def pot_half_btn(self, interaction: discord.Interaction, _):
        if not await self._check_turn(interaction): return
        amt = max(1, self.table.pot // 2)
        ctx = InteractionContext(interaction)
        await self.bot.get_command("raise").callback(ctx, amt)

    @button(label="3/4 Pot", style=discord.ButtonStyle.success)
    async def pot_three_quarter_btn(self, interaction: discord.Interaction, _):
        if not await self._check_turn(interaction): return
        amt = max(1, (self.table.pot * 3) // 4)
        ctx = InteractionContext(interaction)
        await self.bot.get_command("raise").callback(ctx, amt)

    @button(label="Pot", style=discord.ButtonStyle.success)
    async def pot_full_btn(self, interaction: discord.Interaction, _):
        if not await self._check_turn(interaction): return
        amt = max(1, self.table.pot)
        ctx = InteractionContext(interaction)
        await self.bot.get_command("raise").callback(ctx, amt)

    @button(label="All-In", style=discord.ButtonStyle.danger)
    async def allin_btn(self, interaction: discord.Interaction, _):
        if not await self._check_turn(interaction): return
        ctx = InteractionContext(interaction)
        await self.bot.get_command("allin").callback(ctx)

    @button(label="Fold", style=discord.ButtonStyle.secondary)
    async def fold_btn(self, interaction: discord.Interaction, _):
        if not await self._check_turn(interaction): return
        ctx = InteractionContext(interaction)
        await self.bot.get_command("fold").callback(ctx)

        # ---- Help ----
    @discord.ui.button(label="Help", style=discord.ButtonStyle.secondary, custom_id="help_btn")
    async def help_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show help info to any user, regardless of turn."""
        help_text = (
            "**📖 Poker Bot Commands**\n"
            "`!poker start <sb> <bb> <min> <max>` – Create a table\n"
            "`!poker join` – Sit at the table\n"
            "`!poker buyin <amount>` – Buy chips\n"
            "`!poker begin` – Start a hand\n"
            "`!poker status` – Show table state\n"
            "`!poker check / call / raise <amt> / allin / fold` – Play actions\n"
            "`!poker end` – End the table\n\n"
            "💡 You can use buttons for quick actions (Check, Call, Raises, All-in, Fold)!"
        )
        await interaction.response.send_message(help_text, ephemeral=True)

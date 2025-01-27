import disnake
from disnake import file

from disnake.ext import commands
from typing import TYPE_CHECKING

from src.utils.utils import EmbedFactory, ExitButton, add_lines, get_info

if TYPE_CHECKING:
    from src.utils import File


def clear_codeblock(content: str):
    if content.startswith("```"):
        content = "\n".join(content.splitlines()[1:])
    if content.endswith("```"):
        content = content[:-3]
    if content.endswith("\n"):
        content = content[:-1]
    if "`" in content:
        content.replace("`", "\u200b")
    return content


class EditView(disnake.ui.View):
    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        return (
            interaction.author == self.ctx.author
            and interaction.channel == self.ctx.channel
        )

    def __init__(self, ctx, file_: "File", bot_message=None, file_view=None):
        super().__init__()

        self.ctx = ctx
        self.file = file_
        self.content = file_.content
        self.bot_message = bot_message
        self.file_view = file_view
        self.undo = self.file_view.file.undo
        self.redo = self.file_view.file.redo
        self.SUDO = self.ctx.me.guild_permissions.manage_messages

        self.add_item(ExitButton(ctx, bot_message, row=3))

    async def edit(self, inter):
        await inter.response.defer()

        await self.bot_message.edit(
            embed=EmbedFactory.code_embed(
                self.ctx, "".join(add_lines(self.file_view.file.content)), self.file.filename
            ),
        )

    @disnake.ui.button(label="Write", style=disnake.ButtonStyle.gray)
    async def write_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        ...

    @disnake.ui.button(label="Replace", style=disnake.ButtonStyle.gray)
    async def replace_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        await interaction.response.send_message(
            "**Format:**\n[line number]\n```py\n<code>\n```**Example:**"
            "\n12-25\n```py\nfor i in range(10):\n\tprint('foo')\n```",
            ephemeral=True
        )
        content: str = (await self.ctx.bot.wait_for(
            "message",
            check=lambda m: m.author == interaction.author and m.channel == interaction.channel
        )).content
        if content[0].isdigit():
            line_no = content.splitlines()[0]
            if "-" in line_no:
                from_, to = int(line_no.split("-")[0]) - 1, int(line_no.split("-")[1]) - 1
            else:
                from_, to = int(line_no) - 1, int(line_no) - 1
            code = clear_codeblock("\n".join(content.splitlines()[1:]))
        else:
            from_, to = 0, len(self.file_view.file.content) - 1
            code = clear_codeblock(content)
        sliced = self.file_view.file.content.splitlines()
        del sliced[from_:to + 1]
        sliced.insert(from_, code)
        self.file_view.file.content = "\n".join(sliced)

    @disnake.ui.button(label="Append", style=disnake.ButtonStyle.gray)
    async def append_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        await interaction.response.send_message(
            "Type something... (This will append your code with a new line) `[Click save to see the result]`",
            ephemeral=True
        )
        self.undo.append(self.file_view.file.content)
        self.file_view.file.content += "\n" + clear_codeblock((await self.ctx.bot.wait_for(
            "message",
            check=lambda m: m.author == interaction.author and m.channel == interaction.channel
        )).content)

    @disnake.ui.button(label="Rename", style=disnake.ButtonStyle.grey)
    async def rename_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        await interaction.response.send_message(
            "What would you like the filename to be?", ephemeral=True
        )
        filename = await self.bot.wait_for(
            "message",
            check=lambda m: self.ctx.author == m.author
            and m.channel == self.ctx.channel,
        )
        if len(filename.content) > 12:
            if self.SUDO:
                await filename.delete()
            return await interaction.channel.send("That filename is too long! The maximum limit is 12 character")

        file_ = File(filename=filename, content=self.file.content, bot=self.bot)
        description = await get_info(file_)

        self.file = file_
        self.extension = file_.filename.split(".")[-1]

        embed = EmbedFactory.ide_embed(self.ctx, description)
        await self.bot_message.edit(embed=embed)


    @disnake.ui.button(label="Next", style=disnake.ButtonStyle.blurple, row=2)
    async def next_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        ...

    @disnake.ui.button(label="Prev", style=disnake.ButtonStyle.blurple, row=2)
    async def previous_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        ...

    @disnake.ui.button(label="Undo", style=disnake.ButtonStyle.blurple, row=2)
    async def undo_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if not self.undo:
            return await interaction.response.send_message("You have made no changes and have nothing to undo!", ephemeral=True)

        self.redo.append(self.file_view.file.content)
        self.file_view.file.content = self.undo.pop(-1)
        await self.edit(interaction)

    @disnake.ui.button(label="Redo", style=disnake.ButtonStyle.blurple, row=2)
    async def redo_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if not self.redo:
            return await interaction.response.send_message("You have made no changes and have nothing to undo!", ephemeral=True)

        self.undo.append(self.file_view.file.content)
        self.file_view.file.content = self.redo.pop(-1)
        await self.edit(interaction)

    @disnake.ui.button(label="Save", style=disnake.ButtonStyle.green, row=3)
    async def save_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        await self.file_view.third_button.callback(interaction)

    @disnake.ui.button(label="Clear", style=disnake.ButtonStyle.danger, row=3)
    async def clear_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        self.undo.append(self.file_view.file.content)
        self.file_view.file.content = ""

        await self.edit(interaction)

    @disnake.ui.button(label="Back", style=disnake.ButtonStyle.danger, row=3)
    async def settings_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        embed = EmbedFactory.ide_embed(self.ctx, await get_info(self.file))

        await self.bot_message.edit(
            embed=embed,
            view=self.file_view
        )


def setup(bot: commands.Bot):
    pass

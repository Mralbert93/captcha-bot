import asyncio
from captchas import generate_captcha, delete_captcha
import discord
from discord.ext import commands
import os
from timer import get_countdown

captchas = {}

token= os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=';', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        embed = discord.Embed(
            title="Help",
            description="<@1200756820403306586> is a Captcha solving game.\nAnswer the captcha correctly in alloted time or you lose!\n\n`;play` - starts the game\n\nOptions:\n* *length* - the length of the captchas (defaults to 4)\n* *numbers* - whether to display letters and numbers (defaults to False)\n\nSample Usage:\n`;play` - starts a game with default settings\n`;play 4` - starts a game with 4 character captchas\n`;play 4 True` - starts a game with 4 character/number captchas",
            color=discord.Color.blue()
        )

        await ctx.send(embed=embed)

bot.help_command = CustomHelpCommand()

@bot.command(name='play', aliases=['p'])
async def play(ctx, captcha_length: str = "6", characters_and_numbers: str = "False"):
    captcha_info = captchas.get(ctx.channel.id, None)
    if captcha_info:
        await ctx.send(f"<@{ctx.author.id}>, there is already a game running.")
        return
    
    if not captcha_length.isdigit():
        await ctx.send(f"<@{ctx.author.id}>, captcha length must be between 1 and 10.")
        return
    
    captcha_length = int(captcha_length)

    if captcha_length < 1 or captcha_length > 10:
        await ctx.send(f"<@{ctx.author.id}>, captcha length must be between 1 and 10.")
        return
    
    if characters_and_numbers not in {"True", "true"}:
        characters_and_numbers = False
    else:
        characters_and_numbers = True
   
    
    random_string = generate_captcha(captcha_length, characters_and_numbers)
    
    file = discord.File(f"./captchas/{random_string}.png", filename=f"{random_string}.png")
    
    embed = discord.Embed(
        title='Solve the Captcha below',
        description=f'Time is up <t:{get_countdown()}:R>',
    )
    embed.set_image(url=f"attachment://{random_string}.png")

    challenge = await ctx.send(embed=embed, file=file)

    channel_id = ctx.channel.id
    captchas[channel_id] = {
        'captcha_length': captcha_length,
        'characters_and_numbers': characters_and_numbers,
        'captcha_string': random_string,
        'score': 0
    }

    await asyncio.sleep(10)
    if captchas.get(ctx.channel.id, {}).get('captcha_string') == random_string:
        embed.title = "Time is up!"
        embed.description = f"You have lost.\nThe correct answer was **{random_string}**.\n\n**Final Score:** {captchas[ctx.channel.id]['score']}\n\nPlay again with `;p` or `;play`"
        await challenge.edit(embed=embed)
        delete_captcha(random_string)
        del captchas[ctx.channel.id]
    else:
        return

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content != ";p" and message.content != ";play":

        try:
            captcha_info = captchas.get(message.channel.id)
        except Exception as e:
            captcha_info = None

        if captcha_info:
            guess = message.content
            answer = captcha_info['captcha_string']

            if message.content == captcha_info['captcha_string']:
                captchas[message.channel.id]['score'] += 1
                captchas[message.channel.id]['captcha_string'] = ""
                delete_captcha(answer)

                captcha_length = captchas[message.channel.id]['captcha_length']
                characters_and_numbers = captchas[message.channel.id]['characters_and_numbers']
                random_string = generate_captcha(captcha_length, characters_and_numbers)
                
                file = discord.File(f"./captchas/{random_string}.png", filename=f"{random_string}.png")
                
                score = captchas[message.channel.id]['score']
                progress = "🔥" * (int(score/5)+1)
                if score == 0:
                    progress = ""
                
                embed = discord.Embed(
                    title='Solve the Captcha below',
                    description=f"**Score:** {score}\n{progress}\n\nTime is up <t:{get_countdown()}:R>",
                )
                embed.set_image(url=f"attachment://{random_string}.png")

                challenge = await message.channel.send(embed=embed, file=file)

                captchas[message.channel.id]['captcha_string'] = random_string
    
                score = captchas[message.channel.id]['score']
                await asyncio.sleep(10)
                if captchas.get(message.channel.id, {}).get('captcha_string') == random_string:
                    embed.title = "Time is up!"
                    embed.description = f"You have lost.\nThe correct answer was **{random_string}**.\n\n**Final Score:** {captchas[message.channel.id]['score']}\n{progress}\n\nPlay again with `;p` or `;play`"
                    await challenge.edit(embed=embed)
                    delete_captcha(random_string)
                    del captchas[message.channel.id]            
            else:
                score = captchas[message.channel.id]['score']
                progress = "🔥" * (int(score/5)+1)
                if score == 0:
                    progress = ""
                embed = discord.Embed(
                    title="Wrong Answer",
                    description=f"You have lost.\nThe correct answer was **{answer}**.\n\n**Final Score:** {captchas[message.channel.id]['score']}\n{progress}\n\nPlay again with `;p` or `;play`",
                )
                delete_captcha(answer)
                del captchas[message.channel.id]
                await message.channel.send(embed=embed)
                
    await bot.process_commands(message)
    
bot.run(token)

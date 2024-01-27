import asyncio
from captchas import generate_captcha, delete_captcha
from datetime import datetime
import discord
from discord.ext import commands
import os
from pymongo.mongo_client import MongoClient
from pymongo.results import InsertOneResult, UpdateResult
from timer import get_countdown

token= os.environ.get("DISCORD_TOKEN")
database_url = os.environ.get("DATABASE_URL")

mongo = MongoClient(database_url)

db = mongo.captcha
guilds = db["guilds"]

captchas = {}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=';', intents=intents)

async def save_game(guild_id, captcha_length, characters_and_numbers, score):
    game_result = {
        'datetime': datetime.now(),
        'captcha_length': captcha_length,
        'characters_and_numbers': characters_and_numbers,
        'score': score
    }
    guild = guilds.find_one({'_id': guild_id})
    if guild is None:
         guilds.insert_one({'_id': guild_id, 'game_results': [game_result]})
    else:
        guilds.update_one({'_id': guild_id}, {'$push': {'game_results': game_result}}, upsert=True)
    return

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        embed = discord.Embed(
            title="Help",
            description="<@1200756820403306586> is a Captcha solving game.\nAnswer the captcha correctly in alloted time or you lose!\n\n`;play` - starts the game\n\nOptions:\n* *length* - the length of the captchas (defaults to 4)\n* *numbers* - whether to display letters and numbers (defaults to False)\n\nSample Usage:\n`;play` - starts a game with default settings\n`;play 4` - starts a game with 4 character captchas\n`;play 4 True` - starts a game with 4 character/number captchas\n-----\n;`statistics` - shows guild statistics\n-----\n`leaderboard` - shows global leaderboards\n\nContact <@838472003031793684> for support or data deletion requests.",
            color=discord.Color.blue()
        )

        await ctx.send(embed=embed)

bot.help_command = CustomHelpCommand()

@bot.command(name='leaderboard', aliases=['lb'])
async def stats(ctx):
    most_games_query = [
        {"$unwind": "$game_results"},
        {"$group": {"_id": {"guild_id": "$_id"}, "total_games": {"$sum": 1}}},
        {"$sort": {"total_games": -1}},
        {"$limit": 10}
    ]
    top_10_most_games = list(guilds.aggregate(most_games_query))

    most_games_string = ""
    for i, result in enumerate(top_10_most_games, 1):
        guild_id = result["_id"]["guild_id"]
        guild_name = bot.get_guild(guild_id).name
        total_games = result["total_games"]
        most_games_string += f"{i}. {guild_name} ({total_games} games)\n"

    most_sum_query = [
        {"$unwind": "$game_results"},
        {"$group": {"_id": {"guild_id": "$_id"}, "total_score": {"$sum": "$game_results.score"}}},
        {"$sort": {"total_score": -1}},
        {"$limit": 10}
    ]
    top_10_sum_scores = list(guilds.aggregate(most_sum_query))

    most_sum_scores_string = ""
    for i, result in enumerate(top_10_sum_scores, 1):
        guild_id = result["_id"]["guild_id"]
        guild_name = bot.get_guild(guild_id).name
        total_score = result["total_score"]
        most_sum_scores_string += f"{i}. {guild_name} ({total_score})\n"

    high_score_query = [
        {"$unwind": "$game_results"},
        {"$group": {"_id": {"guild_id": "$_id"}, "high_score": {"$max": "$game_results.score"}}},
        {"$sort": {"high_score": -1}},
        {"$limit": 10}
    ]
    top_10_high_scores = list(guilds.aggregate(high_score_query))

    top_high_score_string = ""
    for i, result in enumerate(top_10_high_scores, 1):
        guild_id = result["_id"]["guild_id"]
        guild_name = bot.get_guild(guild_id).name
        high_score = result["high_score"]
        top_high_score_string += f"{i}. {guild_name} ({high_score})\n"

    embed = discord.Embed(
        title='Leaderboard - Most Games Played',
        description=f"{most_games_string}",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=bot.user.avatar.url)
    await ctx.send(embed=embed)

    embed2 = discord.Embed(
        title='Leaderboard - Highest Total Score',
        description=f"{most_sum_scores_string}",
        color=discord.Color.purple()
    )
    embed2.set_thumbnail(url=bot.user.avatar.url)
    await ctx.send(embed=embed2)

    embed3 = discord.Embed(
        title='Leaderboard - Highest Game Score',
        description=f"{top_high_score_string}",
        color=discord.Color.purple()
    )
    embed3.set_thumbnail(url=bot.user.avatar.url)
    await ctx.send(embed=embed3)

@bot.command(name='statistics', aliases=['stats'])
async def statistics(ctx):
    main_query = [
        {'$match': {'_id': ctx.guild.id}},
        {'$unwind': '$game_results'},
        {'$group': {
            '_id': '$_id',
            'top_score': {'$max': '$game_results.score'},
            'average_score': {'$avg': '$game_results.score'},
            'total_score': {'$sum': '$game_results.score'},
            'total_games': {'$sum': 1}
        }},
        {'$project': {'_id': 0, 'top_score': 1, 'average_score': 1, 'total_score': 1, 'total_games': 1}}
    ]
    main_result = list(guilds.aggregate(main_query))

    if main_result:
        embed = discord.Embed(
            title='Guild Statistics',
            description=f"Guild Name: **{ctx.guild.name}**\n\nTotal Games: **{main_result[0]['total_games']}**\nTotal Score: **{main_result[0]['total_score']}**\nAverage Score: **{int(main_result[0]['average_score'])}**\nTop Score: **{main_result[0]['top_score']}**",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=ctx.guild.icon.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"<@ctx.user.id>, no game results found for this guild.")

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
    
    file = discord.File(f"/usr/bot/captcha-bot/captchas/{random_string}.png", filename=f"{random_string}.png")
    
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
        await save_game(ctx.guild.id, captcha_length, characters_and_numbers, 0)
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
                
                file = discord.File(f"/usr/bot/captcha-bot/captchas/{random_string}.png", filename=f"{random_string}.png")
                
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
                    await save_game(message.guild.id, captchas[message.channel.id]['captcha_length'], captchas[message.channel.id]['characters_and_numbers'], captchas[message.channel.id]['score'])
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
                await message.channel.send(embed=embed)
                await save_game(message.guild.id, captchas[message.channel.id]['captcha_length'], captchas[message.channel.id]['characters_and_numbers'], captchas[message.channel.id]['score'])
                delete_captcha(answer)
                del captchas[message.channel.id]
    await bot.process_commands(message)
    
bot.run(token)

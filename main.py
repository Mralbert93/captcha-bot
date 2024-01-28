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
players = db["players"]

captchas = {}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=';', intents=intents)

async def save_game(player_id, guild_id, score):
    game = {
        'datetime': datetime.now(),
        'guild_id': guild_id,
        'score': score
    }

    player = players.find_one({'_id': player_id})
    if player is None:
         players.insert_one({'_id': player_id, 'games': [game]})
    else:
        players.update_one({'_id': player_id}, {'$push': {'games': game}}, upsert=True)
    return

async def get_games_count():
    games_query = [
        {
            "$group": {
                "_id": None,
                "total_score": {"$sum": {"$sum": "$games.score"}}  
            }
        }
    ]

    return list(players.aggregate(games_query))[0]["total_score"]

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

    while True:
            games_count = await get_games_count()
            await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{games_count} Captchas"))
            await asyncio.sleep(60)

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        embed = discord.Embed(
            title="Help",
            description="<@1200756820403306586> is a Captcha solving game.\nAnswer the captcha correctly in alloted time or you lose!\n\n-----\n\n`;play` - starts a game\n\n-----\n\n`statistics` - shows player statistics\n\n-----\n\n`leaderboard` - shows global leaderboards\n\nContact <@838472003031793684> for support or data deletion requests.",
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

bot.help_command = CustomHelpCommand()

@bot.command(name='leaderboard', aliases=['lb'])
async def stats(ctx):
    most_games_query = [
        {"$unwind": "$games"},
        {"$group": {"_id": {"player_id": "$_id"}, "total_games": {"$sum": 1}}},
        {"$sort": {"total_games": -1}},
        {"$limit": 10}
    ]
    top_10_most_games = list(players.aggregate(most_games_query))

    most_games_string = ""
    for i, result in enumerate(top_10_most_games, 1):
        player_id = result["_id"]["player_id"]
        total_games = result["total_games"]
        most_games_string += f"{i}. <@{player_id}> ({total_games} games)\n"

    most_sum_query = [
        {"$unwind": "$games"},
        {"$group": {"_id": {"player_id": "$_id"}, "total_score": {"$sum": "$games.score"}}},
        {"$sort": {"total_score": -1}},
        {"$limit": 10}
    ]
    top_10_sum_scores = list(players.aggregate(most_sum_query))

    most_sum_scores_string = ""
    for i, result in enumerate(top_10_sum_scores, 1):
        player_id = result["_id"]["player_id"]
        total_score = result["total_score"]
        most_sum_scores_string += f"{i}. <@{player_id}> ({total_score})\n"

    high_score_query = [
        {"$unwind": "$games"},
        {"$group": {"_id": {"player_id": "$_id"}, "high_score": {"$max": "$games.score"}}},
        {"$sort": {"high_score": -1}},
        {"$limit": 10}
    ]
    top_10_high_scores = list(players.aggregate(high_score_query))

    top_high_score_string = ""
    for i, result in enumerate(top_10_high_scores, 1):
        player_id = result["_id"]["player_id"]
        high_score = result["high_score"]
        top_high_score_string += f"{i}. <@{player_id}> ({high_score})\n"

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
        {'$match': {'_id': ctx.message.author.id}},
        {'$unwind': '$games'},
        {'$group': {
            '_id': '$_id',
            'top_score': {'$max': '$games.score'},
            'average_score': {'$avg': '$games.score'},
            'total_score': {'$sum': '$games.score'},
            'total_games': {'$sum': 1}
        }},
        {'$project': {'_id': 0, 'top_score': 1, 'average_score': 1, 'total_score': 1, 'total_games': 1}}
    ]
    main_result = list(players.aggregate(main_query))

    rank_query = [
        {
            "$match": {"_id": ctx.message.author.id}
        },
        {
            "$project": {
                "total_score": {"$sum": "$games.score"},
                "top_score": {"$max": "$games.score"}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_score_rank": {"$sum": 1},
                "top_score_rank": {"$sum": 1}
            }
        },
        {
            "$project": {
                "_id": 0,
                "total_score_rank": "$total_score_rank",
                "top_score_rank": "$top_score_rank"
            }
        }
    ]

    rank_result = list(players.aggregate(rank_query))

    if main_result:
        embed = discord.Embed(
            title='Player Statistics',
            color=discord.Color.purple()
        )
        embed.add_field(name='Player Name', value=f"{ctx.author.name}", inline=False)
        embed.add_field(name='Total Games', value=f"{main_result[0]['total_games']}", inline=True)
        embed.add_field(name='Total Score', value=f"{main_result[0]['total_score']}", inline=True)
        embed.add_field(name='High Score', value=f"{main_result[0]['top_score']}", inline=True)
        embed.add_field(name='Accuracy', value=f"{int(main_result[0]['total_score'])/(int(main_result[0]['total_score'])+main_result[0]['total_games'])*100:.2f}%", inline=True)
        embed.add_field(name='Total Score Rank', value=f"#{rank_result[0]['total_score_rank']}", inline=True)
        embed.add_field(name='High Score Rank', value=f"#{rank_result[0]['top_score_rank']}", inline=True)
        embed.set_thumbnail(url=ctx.message.author.avatar.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"<@{ctx.message.author.id}>, no game results found. Get playing!")

@bot.command(name='play', aliases=['p'])
async def play(ctx):
    captcha_info = captchas.get(ctx.message.author.id, None)
    if captcha_info:
        await ctx.send(f"<@{ctx.message.author.id}>, you already are playing a game. Please finish it before starting a new game.")
        return
    
    random_string = generate_captcha()
    
    file = discord.File(f"/usr/bot/captcha-bot/captchas/{random_string}.png", filename=f"{random_string}.png")
    
    embed = discord.Embed(
        title='Solve the Captcha below',
        description=f'<@{ctx.message.author.id}>\n\nTime is up <t:{get_countdown()}:R>',
    )
    embed.set_image(url=f"attachment://{random_string}.png")

    challenge = await ctx.send(embed=embed, file=file)

    player_id = ctx.message.author.id
    captchas[player_id] = {
        'captcha_string': random_string,
        'score': 0
    }

    await asyncio.sleep(10)
    if captchas.get(player_id, {}).get('captcha_string') == random_string:
        embed.title = "Time is up!"
        embed.description = f"<@{player_id}>, you have lost.\nThe correct answer was **{random_string}**.\n\n**Final Score:** {captchas[player_id]['score']}\n\nPlay again with `;p` or `;play`"
        await challenge.edit(embed=embed)
        await save_game(player_id, ctx.guild.id, 0)
        delete_captcha(random_string)
        del captchas[player_id]
    else:
        return

@bot.event
async def on_message(message):
    player_id = message.author.id
    
    if message.author == bot.user:
        return

    if message.channel.id == 1201256347430289619 and message.author.bot:
        user = await bot.fetch_user(message.content)
        user_id = int(user.id)
        player = players.find_one({"_id": user_id})
        if player is None:
            embed = discord.Embed(
                title="Vote Confirmation",
                description=f"Thank you for voting for <@1200756820403306586> on Top.GG.\nIn order to be eligible for vote rewards, please play a game.",
                color=discord.Color.purple()
            )
            await user.send(embed=embed) 
            return
        else:
            players.update_one({"_id": user_id}, {"$inc": {"extra_lives": 10}})
            player = players.find_one({"_id": user_id})
            extra_lives = player["extra_lives"]
            embed = discord.Embed(
                title="Vote Confirmation",
                description=f"Thank you for voting for <@1200756820403306586> on Top.GG.\nYou have received **10 extra lives** as a reward.\nYou now have **{extra_lives}** extra lives to use.\nDon't forget to vote again in 12 hours for more rewards!\n{user.mention}",
                color=discord.Color.purple()
            )
            await user.send(embed=embed) 
            return
        
    if message.content != ";p" and message.content != ";play":

        try:
            captcha_info = captchas.get(player_id)
        except Exception as e:
            captcha_info = None

        if captcha_info:
            guess = message.content
            answer = captcha_info['captcha_string']

            if message.content == captcha_info['captcha_string']:
                captchas[player_id]['score'] += 1
                captchas[player_id]['captcha_string'] = ""
                delete_captcha(answer)

                random_string = generate_captcha()
                
                file = discord.File(f"/usr/bot/captcha-bot/captchas/{random_string}.png", filename=f"{random_string}.png")
                
                score = captchas[player_id]['score']
                progress = "🔥" * (int(score/5)+1)
                if score == 0:
                    progress = ""
                
                embed = discord.Embed(
                    title='Solve the Captcha below',
                    description=f"<@{message.author.id}>\n\n**Score:** {score}\n{progress}\n\nTime is up <t:{get_countdown()}:R>",
                )
                embed.set_image(url=f"attachment://{random_string}.png")

                challenge = await message.channel.send(embed=embed, file=file)

                captchas[player_id]['captcha_string'] = random_string
    
                score = captchas[player_id]['score']
                await asyncio.sleep(10)
                if captchas.get(player_id, {}).get('captcha_string') == random_string:
                    embed.title = "Time is up!"
                    embed.description = f"<@{player_id}>, you have lost.\nThe correct answer was **{random_string}**.\n\n**Final Score:** {captchas[player_id]['score']}\n{progress}\n\nPlay again with `;p` or `;play`"
                    await challenge.edit(embed=embed)
                    await save_game(player_id, message.guild.id, captchas[player_id]['score'])
                    delete_captcha(random_string)
                    del captchas[player_id]
            else:
                score = captchas[player_id]['score']
                progress = "🔥" * (int(score/5)+1)
                if score == 0:
                    progress = ""
                embed = discord.Embed(
                    title="Wrong Answer",
                    description=f"<@{player_id}>, you have lost.\nThe correct answer was **{answer}**.\n\n**Final Score:** {captchas[player_id]['score']}\n{progress}\n\nPlay again with `;p` or `;play`",
                )
                await message.channel.send(embed=embed)
                await save_game(player_id, message.guild.id, captchas[player_id]['score'])
                delete_captcha(answer)
                del captchas[player_id]
    await bot.process_commands(message)
    
bot.run(token)

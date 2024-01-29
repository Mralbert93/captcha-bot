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
role_thresholds = {}

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
         players.insert_one({'_id': player_id, 'games': [game], 'coins': score*10})
    else:
        players.update_one({'_id': player_id}, {'$push': {'games': game}, "$inc": {"coins": score*10}}, upsert=True)
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

async def get_skips(player_id): 
    player_object = players.find_one({"_id": player_id})

    if player_object is None:
        return None
    else:
        return player_object.get("skips")

async def check_roles(player_id):
    guild = bot.get_guild(1201163257461866596)
    player = guild.get_member(player_id)
    
    high_score_query = [
        {'$match': {'_id': player_id}},
        {'$unwind': '$games'},
        {'$group': {
            '_id': '$_id',
            'top_score': {'$max': '$games.score'}
        }},
        {'$project': {'_id': 0, 'top_score': 1}}
    ]
    top_score = list(players.aggregate(high_score_query))[0]['top_score']

    new_roles = {}
    for role, threshold in role_thresholds.items():
        if role is not None and role not in player.roles and top_score >= threshold:
            new_roles.append(role.name)
            player.add_roles(role)
            print(f"{role.name} added for {player_id}")
    return new_roles

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

    guild = bot.get_guild(1201163257461866596)
    
    novice = discord.utils.get(guild.roles, id=1201493503096651816)
    apprentice = discord.utils.get(guild.roles, id=1201493685775368272)
    explorer = discord.utils.get(guild.roles, id=1201493818005016576)
    enthusiast = discord.utils.get(guild.roles, id=1201493908400648273)
    master = discord.utils.get(guild.roles, id=1201493975249465384)
    grandmaster = discord.utils.get(guild.roles, id=1201494061522092092)
    overlord = discord.utils.get(guild.roles, id=1201494156950909010)

    role_thresholds = {
        novice: 10,
        apprentice: 25,
        explorer: 50,
        enthusiast: 100,
        master: 250,
        grandmaster: 500,
        overlord: 1000
    }

    while True:
            games_count = await get_games_count()
            await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{games_count} Captchas"))
            await asyncio.sleep(60)

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        embed = discord.Embed(
            title="Help",
            description="<@1200756820403306586> is a Captcha solving game.\nAnswer the captcha correctly in alloted time or you lose!\n\n`;play` - starts a game\n\n`;skip` - skips the captcha\n\n`;coins` - shows your coin balance\n\n`;buy <quantity>` - buys the a specified amount of skips\n\n`;statistics` - shows player statistics\n\n`;leaderboard` - shows global leaderboards\n\n`;vote` - vote to receive rewards\n\nContact <@838472003031793684> for support or data deletion requests.",
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

    total_score_rank_query = [
        {
            "$unwind": "$games"
        },
        {
            "$group": {
                "_id": "$_id",
                "total_score": {"$sum": "$games.score"}
            }
        },
        {
            "$sort": {
                "total_score": -1
            }
        },
        {
            "$project": {
                "_id": 1,
                "total_score": 1
            }
        }
    ]

    total_score_rank_result = list(players.aggregate(total_score_rank_query))
    total_score_player_index = next((index for index, player in enumerate(total_score_rank_result) if player["_id"] == ctx.message.author.id), None)+1

    high_score_rank_query = [
        {
            "$unwind": "$games"
        },
        {
            "$group": {
                "_id": "$_id",
                "high_score": {"$max": "$games.score"}
            }
        },
        {
            "$sort": {
                "high_score": -1
            }
        },
        {
            "$project": {
                "_id": 1,
                "high_score": 1
            }
        }
    ]

    high_score_rank_result = list(players.aggregate(high_score_rank_query))
    high_score_player_index = next((index for index, player in enumerate(high_score_rank_result) if player["_id"] == ctx.message.author.id), None)+1

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
        embed.add_field(name='Total Score Rank', value=f"#{total_score_player_index}", inline=True)
        embed.add_field(name='High Score Rank', value=f"#{high_score_player_index}", inline=True)
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
            embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/422087909634736160/d41e1166aadbba1fd62f6c43e2a15777.png")
            await user.send(embed=embed) 
            return
        else:
            players.update_one({"_id": user_id}, {"$inc": {"skips": 10}})
            player = players.find_one({"_id": user_id})
            skips = player["skips"]
            embed = discord.Embed(
                title="Vote Confirmation",
                description=f"Thank you for voting for <@1200756820403306586> on Top.GG.\n\nYou have received **10 skips** as a reward.\nYou now have **{skips} skips** to use.\n\nDon't forget to vote again in 12 hours for more rewards!\n\n{user.mention}",
                color=discord.Color.purple()
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/422087909634736160/d41e1166aadbba1fd62f6c43e2a15777.png")
            await user.send(embed=embed) 
            return
        
    if not message.content.startswith(";"):
        try:
            captcha_info = captchas.get(player_id)
        except Exception as e:
            captcha_info = None

        if captcha_info:
            guess = message.content
            answer = captcha_info['captcha_string']

            if message.content.lower() == captcha_info['captcha_string'].lower():
                captchas[player_id]['score'] += 1
                captchas[player_id]['captcha_string'] = ""
                delete_captcha(answer)

                random_string = generate_captcha()
                
                file = discord.File(f"/usr/bot/captcha-bot/captchas/{random_string}.png", filename=f"{random_string}.png")
                
                score = captchas[player_id]['score']
                progress = "🔥" * (int(score/5)+1)
                if score == 0:
                    progress = ""

                skips = await get_skips(player_id)
                
                embed = discord.Embed(
                    title='Solve the Captcha below',
                    description=f"<@{message.author.id}>, you have {skips} skips left.\nYou can use `;skip` or `;s` to skip.\n\n**Score:** {score}\n{progress}\n\nTime is up <t:{get_countdown()}:R>",
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
                    await check_roles(player_id)
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
                await check_roles(player_id)
                
    await bot.process_commands(message)

@bot.command(name='skip', aliases=['s'])
async def skip(ctx):
    player_id = ctx.message.author.id
    try:
        captcha_info = captchas.get(player_id)
    except Exception as e:
        await ctx.send("<@{ctx.author.mention}>, you must be playing a game to use a skip.")
        return

    skips = await get_skips(player_id)
    if skips > 0:
        players.update_one({"_id": player_id}, {"$inc": {"skips": -1}})
        
        captcha_info = captchas.get(player_id)
        answer = captcha_info['captcha_string']
        captchas[player_id]['captcha_string'] = ""
        delete_captcha(answer)

        random_string = generate_captcha()

        file = discord.File(f"/usr/bot/captcha-bot/captchas/{random_string}.png", filename=f"{random_string}.png")
                
        score = captchas[player_id]['score']
        progress = "🔥" * (int(score/5)+1)
        progress += "\n"
        if score == 0:
            progress = ""
                
        embed = discord.Embed(
            title='Solve the Captcha below',
            description=f"<@{ctx.message.author.id}>, you have chosen to skip.\nYou have {skips-1} skips left.\n\n**Score:** {score}\n{progress}\nTime is up <t:{get_countdown()}:R>",
        )
        embed.set_image(url=f"attachment://{random_string}.png")

        challenge = await ctx.send(embed=embed, file=file)

        captchas[player_id]['captcha_string'] = random_string
    
        score = captchas[player_id]['score']
        await asyncio.sleep(10)
        if captchas.get(player_id, {}).get('captcha_string') == random_string:
            embed.title = "Time is up!"
            embed.description = f"<@{player_id}>, you have lost.\nThe correct answer was **{random_string}**.\n\n**Final Score:** {captchas[player_id]['score']}\n{progress}\n\nPlay again with `;p` or `;play`"
            await challenge.edit(embed=embed)
            await save_game(player_id, ctx.message.guild.id, captchas[player_id]['score'])
            delete_captcha(random_string)
            del captchas[player_id]
            await check_roles(player_id)
    else:
        await ctx.send(f"You have no skips left. You can get more skips from `;buy skips` or `;vote`.\n{ctx.author.mention}")
        return

@bot.command(name='vote', aliases=['v'])
async def vote(ctx):
    embed = discord.Embed(
            title="Coins Balance",
            description=f"{ctx.author.mention}\n\nYou can vote every 12 hours for the bot using the link below:\n\nhttps://top.gg/bot/1200756820403306586/vote\n\nAfter voting, you will be automatically rewarded **10 skips**.",
            color=discord.Color.purple()
        )
    embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/422087909634736160/d41e1166aadbba1fd62f6c43e2a15777.png")
    await ctx.send(embed=embed)
    return

@bot.command(name='coins', aliases=['c'])
async def coins(ctx):
    result = players.find_one({'_id': ctx.message.author.id})
    try:
        coins = result["coins"]
        embed = discord.Embed(
            title="Coins Balance",
            description=f"{ctx.author.mention}\n\nYou have **{coins} :coin: coins**.\nKeep playing to get more!",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=ctx.message.author.avatar.url)
        await ctx.send(embed=embed)
        return
    except Exception as e:
        embed = discord.Embed(
            title="Coins Balance",
            description=f"{ctx.author.mention}\n\nYou don't have any :coin: coins.\nStart playing to get some!",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=ctx.message.author.avatar.url)
        await ctx.send(embed=embed)
        return

@bot.command(name='buy', aliases=['b'])
async def buy(ctx, quantity: int = 0):
    if quantity is None or quantity < 1:
        await ctx.send(f"{ctx.message.author.mention}\n\nPlease specify the amount of skips you want to buy.\nEach skip costs 1000 :coin: coins.\n\n`;buy 1`")
        return
    else:
        result = players.find_one({'_id': ctx.message.author.id})
        try:
            coins = result["coins"]
            if coins > (quantity*1000):
                players.update_one({"_id": ctx.message.author.id}, {"$inc": {"coins": -1000 * quantity, "skips": quantity}})
                embed = discord.Embed(
                    title="Skips Purchased",
                    description=f"{ctx.author.mention}\n\nYou have bought {quantity} skips for {1000*quantity} :coin: coins.\nYou have {(coins-(quantity*1000))} :coin: coins left.",
                    color=discord.Color.purple()
                )
                embed.set_thumbnail(url=ctx.message.author.avatar.url)
                await ctx.send(embed=embed)
                return
            else:
                embed = discord.Embed(
                    title="Skip Purchase Failure",
                    description=f"{ctx.author.mention}\n\nYou don't have enough coins.\n\nYou need {1000*quantity} :coin: coins.\nYou have {coins} :coin: coins.",
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url=ctx.message.author.avatar.url)
                await ctx.send(embed=embed)
                return
        except Exception as e:
            embed = discord.Embed(
                title="Skip Purchase Failure",
                description=f"{ctx.author.mention}\n\nYou don't have any :coin: coins to buy skips.\nStart playing to get some!",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=ctx.message.author.avatar.url)
            await ctx.send(embed=embed)
            return
                             
bot.run(token)

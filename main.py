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

guild = None
captchas = {}
role_thresholds = None
novice = None
apprentice = None
explorer = None 
enthusiast = None 
master = None
grandmaster = None
overlord = None 

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=';', intents=intents)

async def save_game(player_id, guild_id, score):
    game = {
        'datetime': datetime.now(),
        'guild_id': guild_id,
        'score': score
    }

    multiplier = await check_for_boost(player_id)
    coins = score*10*multiplier

    player = players.find_one({'_id': player_id})
    if player is None:
         players.insert_one({'_id': player_id, 'games': [game], 'coins': coins})
    else:
        players.update_one({'_id': player_id}, {'$push': {'games': game}, "$inc": {"coins": coins}}, upsert=True)
    return multiplier, coins

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

async def check_roles(player_id, score, channel):
    guild = bot.get_guild(1201163257461866596)
    player = await guild.fetch_member(player_id)
    
    new_roles = []
    for role, threshold in role_thresholds.items():
        if role not in player.roles and score >= threshold:
            new_roles.append(role.name)
            await player.add_roles(role)
            embed = discord.Embed(
                title="New Title Achieved",
                description=f"Congratulations!\nYou earned the **{role.name}** role.\nThis was earned by scoring more than {threshold}!\n\n<@{player_id}>",
                color=discord.Color.purple()
            )
            embed.set_thumbnail(url=player.avatar.url)
            await channel.send(embed=embed)
    return new_roles

async def check_for_boost(player_id):
    try:
        player = await guild.fetch_member(player_id)
    except Exception as e:
        return 1
        
    if player is None:
        return 1

    if player.premium_since is None:
        return 1
    else:
        return 2

async def update_leaderboards(guild):
    lb_channel = guild.get_channel(1201185111815762001)
            
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
        most_games_string += f"{i}. <@{player_id}> - {total_games} games\n"
        
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
        most_sum_scores_string += f"{i}. <@{player_id}> - {total_score}\n"
        
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
        top_high_score_string += f"{i}. <@{player_id}> - {high_score}\n"
        
    embed = discord.Embed(
        title='Leaderboard - High Score',
        description=f"{top_high_score_string}",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="Leaderboards updated hourly here: https://discord.gg/gkpxVhMZqP") 
    await lb_channel.send(embed=embed)
        
    embed2 = discord.Embed(
        title='Leaderboard - Total Score',
        description=f"{most_sum_scores_string}",
        color=discord.Color.purple()
    )
    embed2.set_thumbnail(url=bot.user.avatar.url)
    embed2.set_footer(text="Leaderboards updated hourly here: https://discord.gg/gkpxVhMZqP") 
    await lb_channel.send(embed=embed2)
        
    embed3 = discord.Embed(
        title='Leaderboard - Games Played',
        description=f"{most_games_string}",
        color=discord.Color.purple()
    )
    embed3.set_thumbnail(url=bot.user.avatar.url)
    embed3.set_footer(text="Leaderboards updated hourly here: https://discord.gg/gkpxVhMZqP") 
    await lb_channel.send(embed=embed3)
    return

async def send_message_to_guild_owners():
    for guild in bot.guilds:
        try:
            owner = await bot.fetch_user(guild.owner_id)

            # Send a direct message to the owner
            await owner.send("Hello! My name is <@838472003031793684>, creator of <@1200756820403306586>. I am reaching out to let you know we have identified and resolved a bug that was causing first time players records to fail to save. The bot has been thoroughly tested and should now be working again. If you encounter any other issues, please feel free to report them here:\n\mhttps://discord.gg/Mz8NwHDa")

            print(f"Message sent to the owner of {guild.name}")
        except discord.HTTPException as e:
            print(f"Error sending message to the owner of {guild.name}: {e}")


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

    global guild, novice, apprentice, explorer, enthusiast, master, grandmaster, overlord, role_thresholds
    
    guild = bot.get_guild(1201163257461866596)

    await send_message_to_guild_owners()
    
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

    n = 1
    while True:
        games_count = await get_games_count()
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{games_count} Captchas"))
        if n % 60 == 0:
            await update_leaderboards(guild)
        n += 1
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
        most_games_string += f"{i}. <@{player_id}> - {total_games} games\n"

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
        most_sum_scores_string += f"{i}. <@{player_id}> - {total_score}\n"

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
        top_high_score_string += f"{i}. <@{player_id}> - {high_score}\n"

    embed = discord.Embed(
        title='Leaderboard - High Score',
        description=f"{top_high_score_string}",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="Leaderboards updated hourly here: https://discord.gg/gkpxVhMZqP") 
    await ctx.send(embed=embed)

    embed2 = discord.Embed(
        title='Leaderboard - Total Score',
        description=f"{most_sum_scores_string}",
        color=discord.Color.purple()
    )
    embed2.set_thumbnail(url=bot.user.avatar.url)
    embed2.set_footer(text="Leaderboards updated hourly here: https://discord.gg/gkpxVhMZqP") 
    await ctx.send(embed=embed2)

    embed3 = discord.Embed(
        title='Leaderboard - Games Played',
        description=f"{most_games_string}",
        color=discord.Color.purple()
    )
    embed3.set_thumbnail(url=bot.user.avatar.url)
    embed3.set_footer(text="Leaderboards updated hourly here: https://discord.gg/gkpxVhMZqP") 
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
        embed.set_footer(text="Join our Official Server to earn titles based on high scores: https://discord.gg/gkpxVhMZqP") 
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"<@{ctx.message.author.id}>, no game results found. Get playing!")

@bot.command(name='play', aliases=['p'])
async def play(ctx):
    captcha_info = captchas.get(ctx.message.author.id, None)
    if captcha_info:
        embed = discord.Embed(
                title="Game Already Running",
                description=f"You already are playing a game. Please finish it before starting a new game.\n\n<@{ctx.message.author.id}>",
                color=discord.Color.red()
            )
        embed.set_thumbnail(url="https://i.ibb.co/tptVTTH/toppng-com-red-x-in-circle-x-ico-2000x2000-removebg-preview.png")
        await ctx.send(embed=embed)
        return
    
    random_string = generate_captcha()
    
    file = discord.File(f"/usr/bot/captcha-bot/captchas/{random_string}.png", filename=f"{random_string}.png")
    
    embed = discord.Embed(
        title='Solve the Captcha below',
        description=f'Time is up <t:{get_countdown()}:R>\n\n<@{ctx.message.author.id}>',
        color=discord.Color.purple()
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
        multiplier, coins = await save_game(player_id, ctx.guild.id, 0)
        embed.title = "Time is up!"
        embed.description = f"You have lost.\nThe correct answer was **{random_string}**.\n\n**Final Score:** {captchas[player_id]['score']}\n\nYou earned **{coins} :coin: coins** ({multiplier}x multiplier).\n\nPlay again with `;p` or `;play`\n\n<@{player_id}>"
        await challenge.edit(embed=embed)
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
                if skips is None:
                    skips = 0
                
                embed = discord.Embed(
                    title='Solve the Captcha below',
                    description=f"You have **{skips} skips** left.\nYou can use `;skip` or `;s` to skip.\n\n**Score:** {score}\n{progress}\n\nTime is up <t:{get_countdown()}:R>\n\n<@{message.author.id}>",
                    color=discord.Color.purple()
                )
                embed.set_image(url=f"attachment://{random_string}.png")

                challenge = await message.channel.send(embed=embed, file=file)

                captchas[player_id]['captcha_string'] = random_string
    
                score = captchas[player_id]['score']
                await asyncio.sleep(10)
                if captchas.get(player_id, {}).get('captcha_string') == random_string:
                    multiplier, coins = await save_game(player_id, message.guild.id, captchas[player_id]['score'])
                    embed.title = "Time is up!"
                    embed.description = f"You have lost.\nThe correct answer was **{random_string}**.\n\n**Final Score:** {captchas[player_id]['score']}\n{progress}\n\nYou earned **{coins} :coin: coins** ({multiplier}x multiplier)\n\n<@{player_id}>"
                    embed.set_footer(text="Play again with ;p or ;play")
                    await challenge.edit(embed=embed)
                    delete_captcha(random_string)
                    if message.guild.id == 1201163257461866596:
                        await check_roles(player_id, captchas[player_id]['score'], message.channel)
                    del captchas[player_id]
            else:
                score = captchas[player_id]['score']
                progress = "🔥" * (int(score/5)+1)
                if score == 0:
                    progress = ""
                multiplier, coins = await save_game(player_id, message.guild.id, captchas[player_id]['score'])
                embed = discord.Embed(
                    title="Wrong Answer",
                    description=f"You have lost.\nThe correct answer was **{answer}**.\n\n**Final Score:** {captchas[player_id]['score']}\n{progress}\n\nYou earned **{coins} :coin: coins** ({multiplier}x multiplier).\n\n<@{player_id}>",
                    color=discord.Color.purple()
                )
                embed.set_footer(text="Play again with ;p or ;play")
                await message.channel.send(embed=embed)
                delete_captcha(answer)
                if message.guild.id == 1201163257461866596:
                    await check_roles(player_id, captchas[player_id]['score'], message.channel)
                del captchas[player_id]
                
    await bot.process_commands(message)

@bot.command(name='skip', aliases=['s'])
async def skip(ctx):
    player_id = ctx.message.author.id
    try:
        captcha_info = captchas.get(player_id)
    except Exception as e:
        return

    if captcha_info is None:
        embed = discord.Embed(
            title="Skip Failure",
            description=f"You must be playing a game to use a skip.\n\n{ctx.author.mention}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url="https://i.ibb.co/tptVTTH/toppng-com-red-x-in-circle-x-ico-2000x2000-removebg-preview.png")
        await ctx.send(embed=embed)
        return

    skips = await get_skips(player_id)
    if skips is None:
        skips = 0
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
            description=f"You have chosen to skip.\nYou have **{skips-1} skips** left.\n\n**Score:** {score}\n{progress}\nTime is up <t:{get_countdown()}:R>\n\n<@{ctx.message.author.id}>",
            color=discord.Color.purple()
        )
        embed.set_image(url=f"attachment://{random_string}.png")

        challenge = await ctx.send(embed=embed, file=file)

        captchas[player_id]['captcha_string'] = random_string
    
        score = captchas[player_id]['score']
        await asyncio.sleep(10)
        if captchas.get(player_id, {}).get('captcha_string') == random_string:
            multiplier, coins = await save_game(player_id, ctx.message.guild.id, captchas[player_id]['score'])
            embed.title = "Time is up!"
            embed.description = f"You have lost.\nThe correct answer was **{random_string}**.\n\n**Final Score:** {captchas[player_id]['score']}\n{progress}\n\nYou earned **{coins} :coin: coins** ({multiplier}x multiplier).\n\n<@{player_id}>"
            embed.set_footer(text="Play again with ;p or ;play")
            await challenge.edit(embed=embed)
            delete_captcha(random_string)
            if ctx.message.guild.id == 1201163257461866596:
                new_roles = await check_roles(player_id, captchas[player_id]['score'], ctx.message.channel)
            del captchas[player_id]
    else:
        embed = discord.Embed(
            title="Skip Failure",
            description=f"You have no skips left.\nYou can get more skips from `;buy skips` or `;vote`.\n\n{ctx.author.mention}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url="https://i.ibb.co/tptVTTH/toppng-com-red-x-in-circle-x-ico-2000x2000-removebg-preview.png")
        await ctx.send(embed=embed)
        return

@bot.command(name='vote', aliases=['v'])
async def vote(ctx):
    embed = discord.Embed(
            title="Coins Balance",
            description=f"You can vote every **12 hours** for {bot.user.mention} using the link below.\n\nhttps://top.gg/bot/1200756820403306586/vote\n\nAfter voting, you will be automatically rewarded **10 skips**.\n\n{ctx.author.mention}",
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
            title="Coin Balance",
            description=f"You have **{coins} :coin: coins**.\nKeep playing to get more!\n\n{ctx.author.mention}",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=ctx.message.author.avatar.url)
        await ctx.send(embed=embed)
        return
    except Exception as e:
        embed = discord.Embed(
            title="Coin Balance",
            description=f"You don't have any :coin: coins.\nStart playing to get some!\n\n{ctx.author.mention}",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=ctx.message.author.avatar.url)
        await ctx.send(embed=embed)
        return

@bot.command(name='buy', aliases=['b'])
async def buy(ctx, quantity: int = 0):
    if quantity is None or quantity < 1:
        embed = discord.Embed(
            title="Skip Purchase Failure",
            description=f"Please specify the amount of skips you want to buy.\nEach skip costs **1000 :coin: coins**.\n\n`;buy 1`\n\n{ctx.message.author.mention}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url="https://i.ibb.co/tptVTTH/toppng-com-red-x-in-circle-x-ico-2000x2000-removebg-preview.png")
        await ctx.send(embed=embed)
        return
    else:
        result = players.find_one({'_id': ctx.message.author.id})
        try:
            coins = result["coins"]
            if coins > (quantity*1000):
                players.update_one({"_id": ctx.message.author.id}, {"$inc": {"coins": -1000 * quantity, "skips": quantity}})
                embed = discord.Embed(
                    title="Skips Purchased",
                    description=f"You have bought {quantity} skips for **{1000*quantity} :coin: coins**.\nYou have **{(coins-(quantity*1000))}** :coin: coins left.\n\n{ctx.author.mention}",
                    color=discord.Color.purple()
                )
                embed.set_thumbnail(url="https://i.ibb.co/3kytCr7/2023446-removebg-preview.png")
                await ctx.send(embed=embed)
                return
            else:
                embed = discord.Embed(
                    title="Skip Purchase Failure",
                    description=f"You don't have enough coins.\n\nYou need **{1000*quantity} :coin: coins**.\nYou have **{coins} :coin: coins**.\n\n{ctx.author.mention}",
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url="https://i.ibb.co/tptVTTH/toppng-com-red-x-in-circle-x-ico-2000x2000-removebg-preview.png")
                await ctx.send(embed=embed)
                return
        except Exception as e:
            embed = discord.Embed(
                title="Skip Purchase Failure",
                description=f"You don't have any :coin: coins to buy skips.\nStart playing to get some!\n\n{ctx.author.mention}",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url="https://i.ibb.co/tptVTTH/toppng-com-red-x-in-circle-x-ico-2000x2000-removebg-preview.png")
            await ctx.send(embed=embed)
            return
                             
bot.run(token)

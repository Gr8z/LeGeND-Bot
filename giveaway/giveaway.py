# Lottery was created by Redjumpman for Redbot
# Renamed to Giveaway

# Standard Library
import asyncio
import os
import random
import shutil
import uuid
from copy import deepcopy
from datetime import datetime

# Discord / Red
import discord
from discord.ext import commands
from .utils import checks
from .utils.dataIO import dataIO
from __main__ import send_cmd_help

try:
    from dateutil import parser
    dateutilAvailable = True
except ImportError:
    dateutilAvailable = False

BOTCOMMANDER_ROLES = ["Family Representative", "Clan Manager", "Clan Deputy", "Co-Leader", "Hub Officer", "admin", "Member"]


class Formatter(dict):
    def __missing__(self, key):
        return key


class PluralDict(dict):
    """This class is used to plural strings

    You can plural strings based on the value input when using this class as a dictionary.
    """
    def __missing__(self, key):
        if '(' in key and key.endswith(')'):
            key, rest = key.split('(', 1)
            value = super().__getitem__(key)
            suffix = rest.rstrip(')').split(',')
            if len(suffix) == 1:
                suffix.insert(0, '')
            return suffix[0] if value <= 1 else suffix[1]
        raise KeyError(key)


class Giveaway:
    """Hosts lotteries on the server"""

    def __init__(self, bot):
        self.bot = bot
        self.file_path = "data/giveaway/giveaway.json"
        self.system = dataIO.load_json(self.file_path)
        self.version = "3.0.07"

    @commands.group(name="giveaway", pass_context=True)
    async def giveaway(self, ctx):
        """giveaway Group Command"""

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @giveaway.command(name="delete", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _delete_giveaway(self, ctx, loadout: int):
        """Deletes a giveaway loadout
        This command will completely remove a giveaway loadout slot.
        You cannot delete the default giveaway slot, 0.
        This comand cannot delete a loadout being used in an active giveaway.
        """
        author = ctx.message.author
        settings = self.check_server_settings(author.server)

        if str(loadout) == settings["Config"]["Current Loadout"]:
            return await self.bot.say("I can't delete a loadout that is in use.")

        if not 1 <= loadout < 6:
            return await self.bot.say("You must pick a loadout number in the range of 1-5.")

        await self.bot.say("You are about to delete slot {}. Are you sure you wish to delete "
                           "this loadout?".format(loadout))
        choice = await self.bot.wait_for_message(timeout=25, author=author)

        if choice is None or choice.content.title() != "Yes":
            return await self.bot.say("No response. Canceling deletion.")

        settings["Loadouts"][str(loadout)].clear()
        self.save_system()
        await self.bot.say("Successfully deleted loadout slot {}.".format(loadout))

    @giveaway.command(name="edit", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _edit_giveaway(self, ctx, loadout):
        """Edits a giveaway loadout
        Will allow you to edit any of the parameters attached to a
        giveaway loadout. Editing this loadout while it is being used
        for an on-going giveaway will affect the process.
        """
        author = ctx.message.author
        cancel = ctx.prefix + "cancel"
        settings = self.check_server_settings(author.server)

        if loadout not in ["1", "2", "3", "4", "5"]:
            return await self.bot.say("Invalid loadout. Must be a digit from 1 to 5.")

        if not settings["Loadouts"][loadout]:
            return await self.bot.say("This loadout is empty, therefore you cannot edit it.")

        roles = [role.name for role in ctx.message.server.roles if role.name != '@everyone']

        def d_check(m):
            return m.content.replace(":", "").isdigit() or m.content == cancel

        def w_check(m):
            return m.content.isdigit() and int(m.content) > 0

        def r_check(m):
            return m.content in roles or m.content == "None" or m.content == cancel

        def p_check(m):
            return m.content.isdigit() or not m.content.startswith("-") or m.content == cancel

        menu_content = ("1 - Start Message\n2 - End Message\n3 - Entry Limit\n4 - Prize\n"
                        "5 - Role Requirement\n6 - Timer\n7 - Number of winners\n"
                        "8 - Days on Server\n0 - Exit")

        while True:
            embed = discord.Embed(title="Giveaway Edit Menu", color=0x50bdfe)
            embed.add_field(name="=============", value=menu_content, inline=False)
            embed.set_footer(text="Type a number to edit a loadout setting.\nAdditionally, type"
                                  "{}cancel to exit at anytime.".format(ctx.prefix))
            menu = await self.bot.say(embed=embed)
            choice = await self.bot.wait_for_message(timeout=25, author=author)

            if choice is None:
                end = await self.bot.say("You took too long. Canceling the edit process.")
                await asyncio.sleep(1)
                for msg in [end, menu]:
                    await self.bot.delete_message(msg)
                break

            if choice.content == "0":
                end = await self.bot.say("Exiting giveaway edit system.")
                await asyncio.sleep(1)
                for msg in [end, choice, menu]:
                    await self.bot.delete_message(msg)
                break

            if choice.content == "1":
                for msg in [choice, menu]:
                    await self.bot.delete_message(msg)
                ask = await self.bot.say("What message would you like to set when starting this "
                                         "giveaway? You can insert the following parameters into "
                                         "{Prize}: Shows the prize (if any).\n"
                                         "{Creator}: Person who started the giveaway.\n"
                                         "{Winners}: Number of winners.\n"
                                         "{Role}: Role requirement for entry (if any).\n"
                                         "{DOS}: Days on server required for entry (if any).\n"
                                         "{Timer}: How long the giveaway will be active "
                                         "(if timer set).\n{Limit}: Maximum number of "
                                         "participants (if set).")
                start_message = await self.bot.wait_for_message(timeout=45, author=author)

                if start_message is None:
                    end = await self.bot.say("You took too long. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [end, ask]:
                        await self.bot.delete_message(msg)
                elif start_message.content == cancel:
                    end = await self.bot.say("Returning to the edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [end, start_message, ask]:
                        await self.bot.delete_message(msg)
                else:
                    settings["Loadouts"][loadout]["Start Message"] = start_message.content
                    self.save_system()
                    ret = await self.bot.say("Start message changed. Returning to the edit "
                                             "selection menu.")
                    await asyncio.sleep(1)
                    for msg in [ret, start_message, ask]:
                        await self.bot.delete_message(msg)

            elif choice.content == "2":
                for msg in [choice, menu]:
                    await self.bot.delete_message(msg)
                ask = await self.bot.say("What message would you like to send when ending this "
                                         "giveaway?\nThe following parameters can be added to the "
                                         "message:\n{Prize}: Shows the prize (if any).\n"
                                         "{Creator}: Person who started the giveaway.\n"
                                         "{Winners}: displays winners names.\n")
                end_message = await self.bot.wait_for_message(timeout=35, author=author)

                if end_message is None:
                    end = await self.bot.say("You took too long. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [end, ask]:
                        await self.bot.delete_message(msg)
                elif end_message.content == cancel:
                    end = await self.bot.say("Returning to the edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [end, end_message, ask]:
                        await self.bot.delete_message(msg)
                else:
                    settings["Loadouts"][loadout]["End Message"] = end_message.content
                    self.save_system()
                    ret = await self.bot.say("End message changed. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [ret, end_message, ask]:
                        await self.bot.delete_message(msg)

            elif choice.content == "3":
                for msg in [choice, menu]:
                    await self.bot.delete_message(msg)
                ask = await self.bot.say("Does this giveaway have an entry limit? Set 0 for none.\n"
                                         "*A giveaway will end early if it reaches the limit, "
                                         "regardless of the timer.*")
                limit = await self.bot.wait_for_message(timeout=35, author=author, check=d_check)

                if limit is None:
                    end = await self.bot.say("You took too long. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [end, ask]:
                        await self.bot.delete_message(msg)
                elif limit.content == cancel:
                    end = await self.bot.say("Returning to the edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [end, limit, ask]:
                        await self.bot.delete_message(msg)
                else:
                    settings["Loadouts"][loadout]["Limit"] = int(limit.content)
                    self.save_system()
                    ret = await self.bot.say("Entry limit changed. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [ret, limit, ask]:
                        await self.bot.delete_message(msg)

            elif choice.content == "4":
                for msg in [choice, menu]:
                    await self.bot.delete_message(msg)
                ask = await self.bot.say("What is the prize for this giveaway?\n*A number entry "
                                         "will deposit credits, but can be set to a word or "
                                         "sentence instead.*")
                prize = await self.bot.wait_for_message(timeout=35, author=author, check=p_check)

                if prize is None:
                    end = await self.bot.say("You took too long. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [end, ask]:
                        await self.bot.delete_message(msg)
                elif prize.content == cancel:
                    end = await self.bot.say("Returning to the edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [end, prize, ask]:
                        await self.bot.delete_message(msg)
                else:
                    settings["Loadouts"][loadout]["Prize"] = prize.content
                    self.save_system()
                    ret = await self.bot.say("Prize changed. Returning to the edit selection menu.")

                    await asyncio.sleep(1)
                    for msg in [ret, prize, ask]:
                        await self.bot.delete_message(msg)

            elif choice.content == "5":
                for msg in [choice, menu]:
                    await self.bot.delete_message(msg)
                ask = await self.bot.say("What is the role required to enter?\n*Use None for no "
                                         "role requirement. Must be a role on your server!*")
                role_req = await self.bot.wait_for_message(timeout=35, author=author, check=r_check)

                if role_req is None:
                    end = await self.bot.say("You took too long. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [end, ask]:
                        await self.bot.delete_message(msg)
                elif role_req.content == cancel:
                    end = await self.bot.say("Returning to the edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [end, role_req, ask]:
                        await self.bot.delete_message(msg)
                else:
                    settings["Loadouts"][loadout]["Role"] = role_req.content
                    self.save_system()
                    ret = await self.bot.say("Role requirement changed. Returning to the edit "
                                             "selection menu.")
                    await asyncio.sleep(1)
                    for msg in [ret, role_req, ask]:
                        await self.bot.delete_message(msg)

            elif choice.content == "6":
                for msg in [choice, menu]:
                    await self.bot.delete_message(msg)
                ask = await self.bot.say("What is the timer for this giveaway?\n"
                                         "Use colons to seperate hours, minutes and seconds. For "
                                         "example: 08:30:25, 40, 55:01 are all valid time formats."
                                         "*Setting the timer to 0 requires you to manually end the "
                                         "giveaway.*".format(ctx.prefix))
                timer = await self.bot.wait_for_message(timeout=35, author=author, check=d_check)

                if timer is None:
                    end = await self.bot.say("You took too long. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [end, ask]:
                        await self.bot.delete_message(msg)
                elif timer.content == cancel:
                    end = await self.bot.say("Returning to the edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [end, timer, ask]:
                        await self.bot.delete_message(msg)
                else:
                    lot_time = self.time_converter(timer.content)
                    settings["Loadouts"][loadout]["Timer"] = lot_time
                    self.save_system()
                    ret = await self.bot.say("The timer has changed. Returning to the edit "
                                             "selection menu.")
                    await asyncio.sleep(0.5)
                    for msg in [ret, timer, ask]:
                        await self.bot.delete_message(msg)

            elif choice.content == "7":
                for msg in [choice, menu]:
                    await self.bot.delete_message(msg)
                ask = await self.bot.say("How many winners can there be for this giveaway?")
                winners = await self.bot.wait_for_message(timeout=35, author=author, check=w_check)

                if winners is None:
                    end = await self.bot.say("You took too long. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [end, ask]:
                        await self.bot.delete_message(msg)
                elif winners.content == cancel:
                    end = await self.bot.say("Returning to the edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [end, winners, ask]:
                        await self.bot.delete_message(msg)
                else:
                    settings["Loadouts"][loadout]["Winners"] = int(winners.content)
                    self.save_system()
                    ret = await self.bot.say("The number of winners has changed. Returning to the "
                                             "edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [ret, winners, ask]:
                        await self.bot.delete_message(msg)

            elif choice.content == "8":
                for msg in [choice, menu]:
                    await self.bot.delete_message(msg)

                ask = await self.bot.say("What is the days on server requirement?\n*Set 0 for "
                                         "none.*")
                dos = await self.bot.wait_for_message(timeout=35, author=author, check=d_check)

                if dos is None:
                    end = await self.bot.say("You took too long. Returning to the edit selection "
                                             "menu.")
                    await asyncio.sleep(1)
                    for msg in [end, ask]:
                        await self.bot.delete_message(msg)
                elif dos.content == cancel:
                    end = await self.bot.say("Returning to the edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [end, dos, ask]:
                        await self.bot.delete_message(msg)
                else:
                    settings["Loadouts"][loadout]["DOS"] = int(dos.content)
                    self.save_system()
                    ret = await self.bot.say("The DoS requirement has changed. Returning to the "
                                             "edit selection menu.")
                    await asyncio.sleep(1)
                    for msg in [ret, dos, ask]:
                        await self.bot.delete_message(msg)

    @giveaway.command(name="end", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _end_giveaway(self, ctx):
        """Manually ends a giveaway. Use help on end giveaway for more info
        This command must be used on an active giveaway that does not have a timer set
        or you will be unable to start a new giveaway. This command may also be used
        to end a giveaway which has a timer, early using this command.
        """
        author = ctx.message.author
        settings = self.check_server_settings(author.server)

        if not settings["Config"]["Active"]:
            return await self.bot.say("I can't end a giveaway that hasn't even begun.")

        loadout = settings["Config"]["Current Loadout"]
        load_pref = settings["Loadouts"][loadout]
        end_msg = self.lottery_teardown(settings, load_pref, author.server)
        await self.bot.say("The giveaway is now ending...")
        await asyncio.sleep(5)
        await self.bot.say(end_msg)

    @giveaway.command(name="reset", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _reset_giveaway(self, ctx):
        """Force resets the giveaway system.
        This command does not wipe data, and should only be used if the
        system is experiencing a hang."""
        server = ctx.message.server
        settings = self.check_server_settings(server)

        self.lottery_reset(settings)
        await self.bot.say("System reset.")

    @giveaway.command(name="setup", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _setup_giveaway(self, ctx):
        """Allows you to create custom a giveaway loadout
        This command allows you create a customized giveaway which
        you can save and launch using the giveaway start command.
        You can have up to five custom giveaway loadouts per server.
        The standard giveaway is permenantly saved to slot 0.
        """
        author = ctx.message.author
        cancel = ctx.prefix + "cancel"
        settings = self.check_server_settings(author.server)
        slot = self.find_empty_slot(settings)
        if slot == "Full":
            return await self.bot.say("All giveaway loadout slots are full. In order to create a "
                                      "new loadout you will need to delete an old one. Use the "
                                      "command `{0}giveaway delete` to remove a loadout, or use the "
                                      "{0}giveaway edit command to change an existing "
                                      "loadout.".format(ctx.prefix))
        roles = [role.name for role in ctx.message.server.roles if role.name != '@everyone']

        def digit_check(m):
            return m.content.replace(':', '').isdigit() or m.content == cancel

        def zero_check(m):
            return m.content.isdigit() and int(m.content) > 0

        def role_check(m):
            return m.content in roles or m.content == "None" or m.content == cancel

        def prize_check(m):
            return m.content.isdigit or not m.content.startswith("-") or m.content == cancel

        # -------------------------------------------------------------------------------------
        await self.bot.say("Welcome to giveaway creation process. To exit this process type "
                           "`{}cancel` at any time.\n\nWhat is the timer for this giveaway?\n"
                           "Use colons to seperate hours, minutes and seconds. For "
                           "example: 08:30:25, 40, 55:01 are all valid time formats.\n"
                           "*Setting the timer to 0 requires you to manually end the giveaway.*"
                           "".format(ctx.prefix))
        timer = await self.bot.wait_for_message(timeout=35, author=author, check=digit_check)

        if timer is None:
            await self.bot.say("You took too long. Canceling giveaway creation.")
            return

        if timer.content == cancel:
            await self.bot.say("giveaway creation cancelled.")
            return
        seconds = self.time_converter(timer.content)
        time_fmt = self.time_formatter(seconds)
        await self.bot.say("Ok got it! Setting the timer to {}.".format(time_fmt))
        await asyncio.sleep(2)
        # -------------------------------------------------------------------------------------

        await self.bot.say("What message would you like to set when starting this giveaway? "
                           "You can insert the following parameters into your start message:\n"
                           "{Prize}: Shows the prize (if any).\n"
                           "{Creator}: Person who started the giveaway.\n"
                           "{Winners}: Number of winners.\n"
                           "{Role}: Role requirement for entry (if any).\n"
                           "{DOS}: Days on server required for entry (if any).\n"
                           "{Timer}: How long the giveaway will be active (if timer set).\n"
                           "{Limit}: Maximum number of participants (if set).")
        start_message = await self.bot.wait_for_message(timeout=60, author=author)

        if start_message is None:
            await self.bot.say("You took too long. Canceling giveaway creation.")
            return

        if start_message.content == cancel:
            await self.bot.say("giveaway creation cancelled.")
            return

        await self.bot.say("Ok, thanks!")
        await asyncio.sleep(2)
        # -------------------------------------------------------------------------------------

        await self.bot.say("What is the days on server requirement?\n*Set 0 for none.*")
        dos = await self.bot.wait_for_message(timeout=35, author=author, check=digit_check)

        if dos is None:
            await self.bot.say("You took too long. Canceling giveaway creation.")
            return

        if dos.content == cancel:
            await self.bot.say("giveaway creation cancelled.")
            return

        await self.bot.say("Great. Setting the days on server requirement to "
                           "{}.".format(dos.content))
        await asyncio.sleep(2)
        # -------------------------------------------------------------------------------------

        await self.bot.say("What is the role required to enter?\n*Use None for no role "
                           "requirement. Must be a role on your server!*")
        role_req = await self.bot.wait_for_message(timeout=35, author=author, check=role_check)

        if role_req is None:
            await self.bot.say("You took too long. Canceling giveaway creation.")
            return

        if role_req.content == cancel:
            await self.bot.say("giveaway creation cancelled.")
            return

        await self.bot.say("Ok. This giveaway will require users to have the {} role to "
                           "enter.".format(role_req.content))
        await asyncio.sleep(2)
        # -------------------------------------------------------------------------------------

        await self.bot.say("How many winners can there be for this giveaway?")
        winners = await self.bot.wait_for_message(timeout=35, author=author, check=zero_check)

        if winners is None:
            await self.bot.say("You took too long. Canceling giveaway creation.")
            return

        if winners.content == cancel:
            await self.bot.say("giveaway creation cancelled.")
            return

        await self.bot.say("Got it. This giveaway will have up to {} "
                           "winners.".format(winners.content))
        await asyncio.sleep(2)
        # -------------------------------------------------------------------------------------

        await self.bot.say("Does this giveaway have an entry limit? Set 0 for none.\n*A giveaway "
                           "will end early if it reaches the limit, regardless of the timer.*")
        limit = await self.bot.wait_for_message(timeout=35, author=author, check=digit_check)

        if limit is None:
            await self.bot.say("You took too long. Canceling giveaway creation.")
            return

        if limit.content == cancel:
            await self.bot.say("giveaway creation cancelled.")
            return

        await self.bot.say("Ok. Setting giveaway entry limit to {}.".format(limit.content))
        await asyncio.sleep(2)
        # -------------------------------------------------------------------------------------

        await self.bot.say("What is the prize for this giveaway?\n*A number entry will deposit "
                           "credits, but can be set to a word or sentence instead.*")
        prize = await self.bot.wait_for_message(timeout=35, author=author, check=prize_check)

        if prize is None:
            await self.bot.say("You took too long. Canceling giveaway creation.")
            return

        if prize.content == cancel:
            await self.bot.say("giveaway creation cancelled.")
            return

        await self.bot.say("Got it! Setting giveaway prize to {}.".format(prize.content))
        await asyncio.sleep(2)
        # -------------------------------------------------------------------------------------

        await self.bot.say("Last question. What message would you like to send when ending this "
                           "giveaway?\nThe following parameters can be added to the message:\n"
                           "{Prize}: Shows the prize (if any).\n"
                           "{Creator}: Person who started the giveaway.\n"
                           "{Winners}: displays winners names.\n")
        end_message = await self.bot.wait_for_message(timeout=60, author=author)

        if end_message is None:
            await self.bot.say("You took too long. Canceling giveaway creation.")
            return

        if end_message.content == cancel:
            await self.bot.say("giveaway creation cancelled.")
            return

        await self.bot.say("Alright. Ending message saved!")
        await asyncio.sleep(2)
        # -------------------------------------------------------------------------------------
        slot_data = {
            "DOS": int(dos.content),
            "End Message": end_message.content,
            "Limit": int(limit.content),
            "Prize": prize.content,
            "Role": role_req.content,
            "Start Message": start_message.content,
            "Timer": seconds,
            "Winners": int(winners.content)
        }
        settings["Loadouts"][slot] = slot_data
        self.save_system()

        await self.bot.say("Creation process completed. Saved to loadout slot {}. You can edit "
                           "this loadout at any time using the command "
                           "`{}giveaway edit`.".format(slot, ctx.prefix))

    @giveaway.command(name="signup", pass_context=True)
    async def _signup_giveaway(self, ctx):
        """Signs you up to track giveaway stats.
        You must have the required role to sign-up for stat tracking.
        If you lose the role, or it changes your stats will still be tracked
        and the information can be viewed when you get the role again.

        By default, anyone can sign up.
        """
        author = ctx.message.author
        settings = self.check_server_settings(author.server)

        if author.id in settings["Members"]:
            return await self.bot.say("You are already signed-up to track stats.")

        role = settings["Config"]["Role"]
        if role not in [r.name for r in author.roles]:
            return await self.bot.say("You do not have the required role to track stats.")

        settings["Members"][author.id] = {"Name": author.name, "Entries": 0, "Won": 0}
        self.save_system()

        await self.bot.say("Congratulations {}, you can now start tracking your giveaway stats. "
                           "To view your stats use the command "
                           "{}giveaway stats.".format(author.name, ctx.prefix))

    @giveaway.command(name="start", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _start_giveaway(self, ctx, loadout=None):
        """Starts a giveaway. Use help on giveaway start for more info
        This command defaults to the standard giveaway loadout in slot 0.

        If you wish to use another loadout, specify it when calling the command.
        Additionally, you may change the default loadout using the [p]setgiveaway default command.

        Starting the giveaway will apply all parameters set in the creation
        process.
        """
        author = ctx.message.author
        settings = self.check_server_settings(author.server)

        if settings["Config"]["Active"]:
            return

        if loadout is None:
            loadout = settings["Config"]["Default Loadout"]

        if not self.slot_checker(settings, loadout):
            return await self.bot.say("The load selected or the default loadout ({}) is empty! "
                                      "Please pick another loadout, edit the current, or set a new "
                                      "default loadout.".format(loadout))

        start_params = self.lottery_setup(settings, loadout, author)
        load_pref = settings["Loadouts"][loadout]
        giveaway_id = str(uuid.uuid4())
        settings["Config"]["Lottery ID"] = giveaway_id
        self.save_system()
        msg = await self.bot.say(load_pref["Start Message"].format_map(Formatter(start_params)))

        await self.bot.add_reaction(msg, "🎉")

        if load_pref["Timer"] > 0:
            settings["Config"]["Tracker"] = datetime.utcnow().isoformat()
            self.save_system()
            await asyncio.sleep(load_pref["Timer"])
            if settings["Config"]["Lottery ID"] == giveaway_id:
                end_msg = self.lottery_teardown(settings, load_pref, author.server)
                await asyncio.sleep(5)
                await self.bot.edit_message(msg, end_msg)

    @giveaway.command(name="stats", pass_context=True)
    async def _stats_giveaway(self, ctx):
        """Shows your giveaway stats
        Shows the number of times you have entered and the number
        of times you have won a giveaway."""
        author = ctx.message.author
        settings = self.check_server_settings(author.server)
        if author.id not in settings["Members"]:
            return await self.bot.say("You are not a giveaway member. Only members can view and "
                                      "track stats. Use [p]giveaway signup to join.")
        role = settings["Config"]["Role"]
        if role not in [r.name for r in author.roles]:
            return await self.bot.say("You do not have the required role to view stats.")

        played = settings["Members"][author.id]["Entries"]
        won = settings["Members"][author.id]["Won"]

        embed = discord.Embed(description="Liveaway Stat Tracker", color=0x50bdfe)
        embed.set_author(name=author.name)
        embed.set_thumbnail(url=author.avatar_url)
        embed.add_field(name="Entries", value=played, inline=True)
        embed.add_field(name="Won", value=won, inline=True)
        await self.bot.say(embed=embed)

    @giveaway.command(name="status", pass_context=True)
    async def _status_giveaway(self, ctx):
        """Check if a giveaway is active"""
        author = ctx.message.author
        settings = self.check_server_settings(author.server)
        if settings["Config"]["Active"]:
            ld = settings["Config"]["Current Loadout"]
            timer = settings["Loadouts"][ld]["Timer"]

            if timer == 0:
                remaining = "no time limit"
            else:
                counter = settings["Config"]["Tracker"]
                seconds = timer - (datetime.utcnow() - parser.parse(counter)).seconds
                remaining = "{} remaining".format(self.time_formatter(seconds))

            winners = settings["Loadouts"][ld]["Winners"]
            entry_limit = settings["Loadouts"][ld]["Limit"]
            dos = settings["Loadouts"][ld]["DOS"]
            role_req = settings["Loadouts"][ld]["Role"]
            prize = settings["Loadouts"][ld]["Prize"]
            footer = "There are currently {} users in the giveaway.".format(len(settings["Players"]))

            if author.id in settings["Players"]:
                desc = "You are currently in the giveaway."
            else:
                desc = "You have **not** entered into this giveaway yet."

            embed = discord.Embed(title="Loadout {}".format(ld), description=desc, color=0x50bdfe)
            embed.set_author(name="Giveaway System 3.0")
            embed.add_field(name="Prize", value=prize, inline=True)
            embed.add_field(name="Possible Winners", value=winners, inline=True)
            embed.add_field(name="Role", value=role_req, inline=True)
            embed.add_field(name="Limit", value=entry_limit, inline=True)
            embed.add_field(name="Time Remaining", value=remaining, inline=True)
            embed.add_field(name="Days on Server Required", value=dos, inline=True)
            embed.set_footer(text=footer)
            await self.bot.say(embed=embed)
        else:
            await self.bot.say("There aren't any lotteries running on this server right now.")

    @giveaway.command(name="viewloadout", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _view_giveaway(self, ctx, loadout: int):
        """View the parameters set for a loadout"""

        if loadout not in [0, 1, 2, 3, 4, 5]:
            return await self.bot.say("Invalid loadout. Must be 0-5.")

        server = ctx.message.server
        settings = self.check_server_settings(server)
        loadout = str(loadout)

        if not self.slot_checker(settings, loadout):
            return await self.bot.say("The selected loadout is empty.")

        timer = settings["Loadouts"][loadout]["Timer"]
        if timer == 0:
            time_fmt = "no time limit"
        else:
            time_fmt = self.time_formatter(timer)

        winners = settings["Loadouts"][loadout]["Winners"]
        entry_limit = settings["Loadouts"][loadout]["Limit"]
        dos = settings["Loadouts"][loadout]["DOS"]
        role_req = settings["Loadouts"][loadout]["Role"]
        prize = settings["Loadouts"][loadout]["Prize"]
        start_msg = settings["Loadouts"][loadout]["Start Message"]
        end_msg = settings["Loadouts"][loadout]["End Message"]

        embed = discord.Embed(title="Loadout {}".format(loadout), color=0x50bdfe)
        embed.add_field(name="Prize", value=prize, inline=True)
        embed.add_field(name="Number of Winners", value=winners, inline=True)
        embed.add_field(name="Role", value=role_req, inline=True)
        embed.add_field(name="Entry Limit", value=entry_limit, inline=True)
        embed.add_field(name="Timer", value=time_fmt, inline=True)
        embed.add_field(name="Days on Server Required", value=dos, inline=True)
        embed.add_field(name="Start Message", value=start_msg, inline=True)
        embed.add_field(name="End Message", value=end_msg, inline=True)
        await self.bot.say(embed=embed)

    @commands.group(name="setGiveaway", pass_context=True)
    async def setgiveaway(self, ctx):
        """giveaway Settings"""

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setgiveaway.command(name="default", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _default_setgiveaway(self, ctx, loadout: int):
        """Changes the default loadout when starting a giveaway
        This loadout will run when no other loadout has been specified.
        In addition, this loadout will run if an invalid loadout is chosen.

        If you have not setup up a loadout, use the command giveaway setup.
        You cannot set a loadout as a default if it has not been setup.

        The factory default is 0.
        """
        if loadout not in [0, 1, 2, 3, 4, 5]:
            return await self.bot.say("Invalid loadout. Must be 0-5.")

        server = ctx.message.server
        settings = self.check_server_settings(server)

        settings["Config"]["Default Loadout"] = str(loadout)
        self.save_system()
        await self.bot.say("Setting the default loadout to {}".format(loadout))

    @setgiveaway.command(name="role", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _role_setgiveaway(self, ctx, role: discord.Role):
        """Sets the role required to track and view stats.
        Must be a role that exists on your server. If you delete this role
        you will need to update giveaway with this command to the new role.
        Otherwise, no one will be able to view their stats, but it will still
        track if they were able to signup.

        By default this command is set to @everyone, and anyone can join.
        """
        server = ctx.message.server
        settings = self.check_server_settings(server)
        settings["Config"]["Role"] = role.name
        self.save_system()
        await self.bot.say("Changed the membership role to {}".format(role.name))

    # ================== Helper Functions ===================================

    async def on_reaction_add(self, reaction, user):
        if reaction.emoji != "🎉":
            return

        if not reaction.message.channel.is_private and self.bot.user.id != user.id:
            settings = self.check_server_settings(user.server)

            if not settings["Config"]["Active"]:
                return

            if user.id in settings["Players"]:
                return

            loadout = settings["Config"]["Current Loadout"]
            load_pref = settings["Loadouts"][loadout]
            players_init = len(settings["Players"])
            result = self.check_requirements(reaction.message, user, players_init, load_pref)
            if result != "True":
                return

            settings["Players"][user.id] = {"Name": user.name}
            players = len(settings["Players"])
            self.update_entries(settings, user.id)
            self.save_system()

            if load_pref["Limit"] != 0:
                if load_pref["Limit"] <= players:
                    await asyncio.sleep(10)

                    end_msg = self.lottery_teardown(settings, load_pref, user.server)
                    await self.bot.edit_message(reaction.message, end_msg)

    def save_system(self):
        dataIO.save_json(self.file_path, self.system)

    def check_requirements(self, message, author, players, loadout):
        role_req = loadout["Role"]
        dos = loadout["DOS"]
        prize = loadout["Prize"]

        try:
            set_prize = int(prize)
        except ValueError:
            set_prize = prize

        try:
            bank = self.bot.get_cog("Economy").bank
        except AttributeError:
            msg = "Economy cog is not loaded, therefore I cannot enter you into the giveaway."
            return msg

        if role_req not in [r.name for r in author.roles] and role_req != "None":
            msg = "You do not meet the role requirement for the giveaway."
        elif (message.timestamp - author.joined_at).days < dos:
            msg = "You do not meet the time on server requirement for this giveaway."
        elif 0 < loadout["Limit"] <= players:
            msg = "You can't join, the giveaway has reached the entry limit, wait for it to end."
        elif isinstance(set_prize, int):
            if not bank.account_exists(author):
                msg = ("You do not have a bank account. You must register for an account to "
                       "participate in lotteries. Everyone please **shame** {} in chat for making "
                       "me write this error exception.".format(author.name))
            else:
                msg = "True"
        else:
            msg = "True"
        return msg

    def check_server_settings(self, server):
        if server.id not in self.system["Servers"]:
            default = {
                "Config": {
                    "Active": False,
                    "Creator": "",
                    "Current Loadout": None,
                    "Default Loadout": "0",
                    "Role": "@everyone",
                    "Lottery ID": 0,
                    "Tracker": 0,
                    "Version": 3.07
                },
                "Members": {},
                "Players": {},
                "Loadouts": {
                    "0": {
                        "DOS": 30,
                        "End Message": ("Congratulations to {Winners}. You have won {Prize} "
                                        "credits! This has been brought to you by {Creator}."),
                        "Limit": 0,
                        "Prize": "500",
                        "Role": "None",
                        "Start Message": ("A giveaway has been started! The prize has "
                                          "been set to {Prize} credits. There can be only "
                                          "{Winners} winner. The only requirement is that you "
                                          "must have at least {DOS} days on the server. "
                                          "There will be a timer of {Timer}, so enter before it "
                                          "ends!"),
                        "Timer": 30,
                        "Winners": 1},
                    "1": {},
                    "2": {},
                    "3": {},
                    "4": {},
                    "5": {}
                }
            }
            self.system["Servers"][server.id] = default
            self.save_system()
            path = self.system["Servers"][server.id]
            print("Creating default giveaway settings for Server: {}".format(server.name))
            return path
        else:
            path = self.system["Servers"][server.id]
            return path

    def distribute_prize(self, selected_winners, server, prize):
        bank = self.bot.get_cog("Economy").bank
        mobjs = [server.get_member(uid) for uid in selected_winners]
        for obj in mobjs:
            bank.deposit_credits(obj, prize)

    def find_empty_slot(self, settings):
        try:
            loadouts = settings["Loadouts"]
            slot = sorted([slot for slot in loadouts if not loadouts[slot]])[0]
        except IndexError:
            slot = "Full"
        return slot

    def lottery_reset(self, settings):
        settings["Config"]["Creator"] = ""
        settings["Config"]["Tracker"] = 0
        settings["Config"]["Current Loadout"] = None
        settings["Config"]["Active"] = False
        settings["Players"].clear()
        settings["Config"]["Lottery ID"] = 0
        self.save_system()

    def lottery_setup(self, settings, loadout, author):
        settings["Config"]["Active"] = True
        settings["Config"]["Creator"] = author.name

        load_pref = settings["Loadouts"][loadout]
        start_params = deepcopy(load_pref)
        start_params["Creator"] = author.name
        start_params["Timer"] = self.time_formatter(start_params["Timer"])

        settings["Config"]["Current Loadout"] = loadout
        self.save_system()
        return start_params

    def lottery_teardown(self, settings, load_pref, server):
        players = settings["Players"]

        # Remove people that left the server during a giveaway. Seriously, who does that!
        filtered_players = [player for player in players.keys()
                            if server.get_member(player) is not None]

        if len(players) == 0 or not filtered_players:
            end_msg = ("Oh no! No one joined the giveaway. I'll reset the system so you can try "
                       "again later.")
            self.lottery_reset(settings)
            return end_msg

        creator = settings["Config"]["Creator"]
        prize = load_pref["Prize"]

        winners = load_pref["Winners"]

        sample = min(len(filtered_players), winners)
        selected_winners = random.sample(filtered_players, sample)
        winners_names = [server.get_member(x).mention for x in selected_winners]
        params = {"Prize": prize, "Creator": creator, "Winners": ", ".join(winners_names)}

        if prize.isdigit():
            self.distribute_prize(selected_winners, server, int(prize))

        end_msg = load_pref["End Message"].format_map(Formatter(params))
        self.update_wins(settings, selected_winners)
        self.lottery_reset(settings)
        return end_msg

    def slot_checker(self, settings, slot):
        try:
            loadout = settings["Loadouts"][slot]
            if not loadout:
                return False
            else:
                return True
        except KeyError:
            return False

    def time_formatter(self, seconds):
        if seconds == 0:
            msg = "no timer"
            return msg

        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        data = PluralDict({'hour': h, 'minute': m, 'second': s})

        if h > 0:
            fmt = "{hour} hour{hour(s)}"
            if data["minute"] > 0 and data["second"] > 0:
                fmt += ", {minute} minute{minute(s)}, and {second} second{second(s)}"
            else:
                fmt += ", and {second} second{second(s)} remaining"
            msg = fmt.format_map(data)
        elif h == 0 and m > 0:
            if data["second"] == 0:
                fmt = "{minute} minute{minute(s)} remaining"
            else:
                fmt = "{minute} minute{minute(s)}, and {second} second{second(s)}"
            msg = fmt.format_map(data)
        else:
            fmt = "{second} second{second(s)}"
            msg = fmt.format_map(data)

        return msg

    def time_converter(self, units):
        return sum(int(x) * 60 ** i for i, x in enumerate(reversed(units.split(":"))))

    def update_wins(self, settings, players):
        for player in players:
            try:
                settings["Members"][player]["Won"] += 1
            except KeyError:
                pass

    def update_entries(self, settings, player):
        try:
            settings["Members"][player]["Entries"] += 1
        except KeyError:
            pass


def check_folders():
    if not os.path.exists("data/giveaway"):
        print("Creating giveaway folder")
        os.makedirs("data/giveaway")

    if os.path.exists("data/JumperCogs/giveaway"):
        try:
            shutil.rmtree("data/JumperCogs/giveaway")
        except PermissionError:
            print("Could not remove the old directory because you are not an admin\n"
                  "Or you have the file open for some reason.")


def check_files():
    default = {"Servers": {}}

    f = "data/giveaway/giveaway.json"

    if not dataIO.is_valid_json(f):
        print("Adding giveaway.json to data/giveaway/")
        dataIO.save_json(f, default)


def setup(bot):
    check_folders()
    check_files()
    if not dateutilAvailable:
        raise RuntimeError("You need to install the library python-dateutil.")
    else:
        n = Giveaway(bot)
        bot.add_cog(n)

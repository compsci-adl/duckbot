from discord import app_commands, Interaction


class FNGGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="fng", description="FNG Group")

    @app_commands.command(name="food", description="Outputs the date of the next Friday Night Games with food")
    async def food(self, interaction: Interaction):
        import datetime as dt

        #Manually inputting dates
        dateStack=[dt.datetime(2024,10,25,17), dt.datetime(2024,8,30,17), dt.datetime(2024,7,26,17), dt.datetime(2024,5,31,17), dt.datetime(2024,4,26,17), dt.datetime(2024,3,29,17)]

        #Checking if the tail date has already passed
        currDate=dt.datetime.now()
        if currDate>dateStack[-1]:
            while len(dateStack)>0 and currDate>dateStack[-1]: #length check was added to prevent access of first element when list was empty - this would cause a compiler error
                dateStack.pop()

        #Printing next time for Games Night
        if len(dateStack)==0:
            await interaction.response.send_message("The next Friday Night Games with food will be next year. Thank you for being a valued member!")

        #Determining if games night is on the same day as day of function call
        timeDifference=dateStack[-1] - currDate
        if timeDifference.days<=1:
            timeDifferenceHours=round(timeDifference.seconds/3600, 2)
            if timeDifferenceHours<1:
                await interaction.response.send_message(f"The next Friday Night Games with food is on today in {timeDifferenceHours} hour at 5pm. Join us in the Duck Lounge!")
            else:
                await interaction.response.send_message(f"The next Friday Night Games with food is on today in {timeDifferenceHours} hours at 5pm. Join us in the Duck Lounge!")
            
        #Determining if games night is on the next day of function call
        if timeDifference.days<2 and timeDifference.days>1:
            await interaction.response.send_message(f"The next Friday Night Games with food is on tomorrow. Join us in the Duck Lounge at 5pm!")
            
        #Determining whether date needs a st, nd, rd or rth
        if (dateStack[-1].strftime('%d') in {1,21,31}): #st
            await interaction.response.send_message(f"The next Friday Night Games with food will be held in {timeDifference.days} days on the {dateStack[-1].strftime('%d')}st of {dateStack[-1].strftime('%B')}") 
        elif (dateStack[-1].strftime('%d') in {2,22}): #nd
            await interaction.response.send_message(f"The next Friday Night Games with food will be held in {timeDifference.days} days on the {dateStack[-1].strftime('%d')}nd of {dateStack[-1].strftime('%B')}") 
        elif (dateStack[-1].strftime('%d') in {3,23}): #rd
            await interaction.response.send_message(f"The next Friday Night Games with food will be held in {timeDifference.days} days on the {dateStack[-1].strftime('%d')}rd of {dateStack[-1].strftime('%B')}") 
        else: #th
            await interaction.response.send_message(f"The next Friday Night Games with food will be held in {timeDifference.days} days on the {dateStack[-1].strftime('%d')}th of {dateStack[-1].strftime('%B')}")     


fng_group = FNGGroup()
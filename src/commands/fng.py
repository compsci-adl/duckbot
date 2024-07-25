from discord import app_commands, Interaction
import datetime as dt


class FNGGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name = "fng", description = "Outputs the date of the next Friday Night Games with food")

    @app_commands.command(name = "food", description = "Outputs the date of the next Friday Night Games with food")
    async def food(self, interaction: Interaction):
        # Manually inputting dates
        date_stack = [dt.datetime(2024,10,25,17), dt.datetime(2024,8,30,17), dt.datetime(2024,7,26,17), dt.datetime(2024,5,31,17), dt.datetime(2024,4,26,17), dt.datetime(2024,3,29,17)]

        # Checking if the tail date has already passed
        curr_date = dt.datetime.now()
        if curr_date>date_stack[-1]:
            while len(date_stack)>0 and curr_date>date_stack[-1]: # length check was added to prevent access of first element when list was empty - this would cause a compiler error
                date_stack.pop()

        # Printing next time for Games Night
        if len(date_stack) == 0:
            await interaction.response.send_message("The next Friday Night Games with food will be next year. Thank you for being a valued member!")

        # Determining if games night is on the same day as day of function call
        time_difference = date_stack[-1].date() - curr_date.date()
        if time_difference.days <= 1:
            time_difference_hours = round(time_difference.seconds/3600, 2)
            if time_difference_hours<1:
                await interaction.response.send_message(f"The next Friday Night Games with food is on today in {time_difference_hours} hour at 5pm. Join us in the Duck Lounge!")
            else:
                await interaction.response.send_message(f"The next Friday Night Games with food is on today in {time_difference_hours} hours at 5pm. Join us in the Duck Lounge!")
            
        # Determining if games night is on the next day of function call
        if time_difference.days<2 and time_difference.days>1:
            await interaction.response.send_message(f"The next Friday Night Games with food is on tomorrow. Join us in the Duck Lounge at 5pm!")
            
        # Determining whether date needs a st, nd, rd or rth
        date_num = date_stack[-1].strftime('%d')
        date_day = date_stack[-1].strftime('%B')
        if (date_num in {1,21,31}): # st
            await interaction.response.send_message(f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}st of {date_day}") 
        elif (date_num in {2,22}): # nd
            await interaction.response.send_message(f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}nd of {date_day}") 
        elif (date_num in {3,23}): # rd
            await interaction.response.send_message(f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}rd of {date_day}") 
        else: # th
            await interaction.response.send_message(f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}th of {date_day}")     


fng_group = FNGGroup()
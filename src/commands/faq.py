from discord import app_commands, Interaction


class FaqGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="faq", description="Answers to common questions")

    @app_commands.command(name="rsp", description="Learn about RSP")
    async def rsp(self, interaction: Interaction):
        rsp_info = ("Participating in RSP (Ravi's Study Program) could possibly be the single most beneficial thing you can do while you're at University to land a job as a Software Engineer at a great company.\n\n"
                    "The program is run by current and former students and tutors from The University of Adelaide, and provides students with the exact steps they need to take to prepare themselves to pass interviews at big tech/FAANG companies. There are very impressive numbers of people that land internships at these companies after successfully completing the program.\n\n"
                    "RSP is an intensive programming bootcamp run each summer break. If you wish to get involved, keep an eye out for flyers on campus towards the end of Semester 2, as well as advertisements that are posted in various computer science related discord servers.\n")
        await interaction.response.send_message(rsp_info)

    @app_commands.command(name="cpc", description="Learn about CPC")
    async def cpc(self, interaction: Interaction):
        cpc_info = ("The Competitive Programming Club (CPC) is the University of Adelaide's home for competitive programming. Whether you're just getting started, or looking to flex those programming muscles, the CPC offers a wide range of events and opportunities for those interested.\n\n"
                    "There's no cost for registration and you can find out more here:\n"
                    "https://acpc.io/\n")
        await interaction.response.send_message(cpc_info)


faq_group = FaqGroup()

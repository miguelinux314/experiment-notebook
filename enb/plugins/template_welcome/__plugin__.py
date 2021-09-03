import enb.plugins

class WelcomeTemplate(enb.plugins.Template):
    """Template intended as an introduction project for enb.
    """
    name = "welcome"
    author = ["Miguel Hernández-Cabronero"]
    label = "Welcome project introducing enb"
    tags = {"project", "demo"}
    tested_on = {"linux"}
    required_fields_to_help = {"user_name": "Your name here"}

import requests
import json
from datetime import datetime

# --- Configuration ---
# Your WoW Audit API Authorization header
API_AUTHORIZATION_HEADER = "e67d56fa410ec7ac9bbc3856b274f32a482005092c52f558ba4c49afe87b935e"

# Required value for dungeon option_1 and option_2
REQUIRED_DUNGEON_OPTION_VALUE = 662

# Discord Webhook URL
# IMPORTANT: In a real GitHub Action, you should store this in a GitHub Secret.
# For example: DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1397519619744469102/PM8ARp8O0T5W4Qm8K_b_Hu7HjB587-rljekb_lIck4gXvrbzwobKHhmqngMNXWNeq4Lq"

# Set this to a specific period ID (e.g., 1020) for testing with historical data.
# Set to None to automatically fetch the current period and then subtract 1.
TEST_PERIOD = 1020 # Change to None for live previous period, e.g., TEST_PERIOD = None

# --- Function to Send Message to Discord Webhook ---
def send_discord_webhook(message, webhook_url, embed_title="M+ Requirement Update", embed_color=3447003):
    """
    Sends a message to a Discord webhook as an embed.

    Args:
        message (str): The main content for the embed's description.
        webhook_url (str): The Discord webhook URL.
        embed_title (str): The title of the Discord embed.
        embed_color (int): The decimal color code for the embed sidebar.
    """
    max_message_length = 4096  # Discord embed description limit

    if not message:
        print("Error: Discord embed description is empty. Not sending.")
        return

    if len(message) > max_message_length:
        print(f"Warning: Discord embed description exceeds {max_message_length} characters. It might be truncated or rejected.")
        # message = message[:max_message_length] # Uncomment to truncate if preferred

    # Construct the embed object
    embed = {
        "title": embed_title,
        "description": message,
        "color": embed_color,
        "timestamp": datetime.utcnow().isoformat() + "Z" # ISO 8601 format for Discord timestamp
    }

    # Construct the main JSON payload with the embed
    payload = {
        "embeds": [embed]
    }

    print(f"DEBUG: Attempting to send Discord embed. Embed title: {embed_title}")
    print(f"DEBUG: Webhook URL: {webhook_url}")
    print(f"DEBUG: JSON Payload (string): {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        print("Discord webhook message (embed) sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to send Discord webhook message: {e}")
        if e.response is not None:
            print(f"Discord API Error Message: {e.response.text}")
        # In a GitHub Action, you might want to exit with a non-zero code here
        # sys.exit(1)


# --- Main Script Logic ---
def main():
    period_to_use = None

    # Step 1: Determine the period to use
    if TEST_PERIOD is not None:
        period_to_use = TEST_PERIOD
        print(f"Using specified test period: {period_to_use}")
    else:
        print("Fetching current period from API...")
        period_api_url = 'https://wowaudit.com/v1/period'
        headers = {
            "accept": "application/json",
            "Authorization": API_AUTHORIZATION_HEADER
        }

        try:
            response = requests.get(period_api_url, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors
            period_data = response.json()

            current_period_from_api = period_data.get("current_period")

            if current_period_from_api is None:
                raise ValueError(f"Could not find 'current_period' in the response from {period_api_url}. Response: {json.dumps(period_data)}")

            # Calculate the previous period
            period_to_use = current_period_from_api - 1
            print(f"Current period retrieved: {current_period_from_api}. Using previous period for data: {period_to_use}")

        except requests.exceptions.RequestException as e:
            print(f"Error: An error occurred while fetching the current period: {e}")
            if e.response is not None:
                print(f"Response Content: {e.response.text}")
            exit(1) # Exit the script on critical error
        except ValueError as e:
            print(f"Error: {e}")
            exit(1) # Exit the script on critical error

    # Step 2: Use the determined period to get historical data
    print(f"Fetching historical data for period: {period_to_use}")
    historical_data_url = f"https://wowaudit.com/v1/historical_data?period={period_to_use}"
    headers = {
        "accept": "application/json",
        "Authorization": API_AUTHORIZATION_HEADER
    }

    try:
        response = requests.get(historical_data_url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        historical_data_response = response.json()

        print("API Call for Historical Data Successful!")
        # print(f"--- Historical Data Response ---\n{json.dumps(historical_data_response, indent=2)}") # Uncomment for full raw response

        # Step 3: Filter the historical data based on vault_options
        print("\n--- Filtering Data ---")
        players_to_report = []

        # Access the array of data items from the 'characters' property.
        data_items = historical_data_response.get("characters", [])

        print(f"DEBUG: Processed {len(data_items)} total player items.")

        for item in data_items:
            name = item.get("name")
            dungeon_vault_option = None

            # Check if 'data', 'vault_options', and 'dungeons' exist
            if item.get("data") and item["data"].get("vault_options") and item["data"]["vault_options"].get("dungeons"):
                dungeon_vault_option = item["data"]["vault_options"]["dungeons"]

            report_player = True
            status_details = None

            if dungeon_vault_option:
                option1 = dungeon_vault_option.get("option_1")
                option2 = dungeon_vault_option.get("option_2")

                if option1 == REQUIRED_DUNGEON_OPTION_VALUE and option2 == REQUIRED_DUNGEON_OPTION_VALUE:
                    report_player = False
                else:
                    status_details = {
                        "Option1": option1,
                        "Option2": option2
                    }
            else:
                status_details = "No 'dungeons' vault option found."

            if report_player:
                players_to_report.append({
                    "PlayerName": name,
                    "DungeonVaultStatus": status_details
                })

        print(f"DEBUG: Found {len(players_to_report)} players who do NOT have 'dungeons' vault option_1 and option_2 both set to {REQUIRED_DUNGEON_OPTION_VALUE}.")

        print(f"\nPlayers who do NOT have 'dungeons' vault option_1 and option_2 both set to {REQUIRED_DUNGEON_OPTION_VALUE} (Console Output):")
        if players_to_report:
            for player in players_to_report:
                print(f"Player: {player['PlayerName']}")
                if isinstance(player['DungeonVaultStatus'], dict):
                    print(f"  Dungeons Options: Option 1: {player['DungeonVaultStatus']['Option1']}, Option 2: {player['DungeonVaultStatus']['Option2']}")
                else:
                    print(f"  Status: {player['DungeonVaultStatus']}")
                print("") # Add a blank line for readability
        else:
            print(f"All players in the data have at least one 'dungeons' vault option with both option_1 and option_2 set to {REQUIRED_DUNGEON_OPTION_VALUE}, or no data was processed.")

        # Step 4: Prepare and Send Discord Webhook Message (as an Embed)
        if DISCORD_WEBHOOK_URL != 'YOUR_DISCORD_WEBHOOK_URL_HERE' and DISCORD_WEBHOOK_URL:
            embed_description = "Følgende spillere mangler forsat at klare deres m+ requirement inden reset:\n\n"

            if players_to_report:
                for player in players_to_report:
                    embed_description += f"{player['PlayerName']}\n"
                embed_title = "M+ Requirement: Manglende Spillere"
                embed_color = 15548997 # Red color (decimal) for incomplete
            else:
                embed_description = "Alle spillere har klaret deres m+ requirement inden reset. Godt arbejde!"
                embed_title = "M+ Requirement: Alle Klaret!"
                embed_color = 3066993 # Green color (decimal) for complete

            send_discord_webhook(embed_description, DISCORD_WEBHOOK_URL, embed_title, embed_color)
        else:
            print("Warning: Discord webhook URL is not configured. Skipping Discord notification.")

    except requests.exceptions.RequestException as e:
        print(f"Error: An error occurred during the historical data API call: {e}")
        if e.response is not None:
            print(f"Response Content: {e.response.text}")
        exit(1) # Exit the script on critical error

if __name__ == "__main__":
    main()

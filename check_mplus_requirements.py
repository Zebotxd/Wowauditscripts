import requests
import json
from datetime import datetime
import os # Import the os module to access environment variables

# --- Configuration ---
# Your WoW Audit API Authorization header
# IMPORTANT: This is now retrieved from a GitHub Secret named WOWAUDIT_API_KEY.
# Do NOT hardcode your API key here if this script is in a public repository.
API_AUTHORIZATION_HEADER = os.getenv('WOWAUDIT_API_KEY')

# Required value for dungeon option_1 and option_2
REQUIRED_DUNGEON_OPTION_VALUE = 662

# Discord Webhook URL
# IMPORTANT: This is now retrieved from a GitHub Secret named DISCORD_WEBHOOK_URL.
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# Path to the Discord ID mapping file
DISCORD_ID_MAP_FILE = 'discord_id_map.json'
DISCORD_ID_MAP = {} # This will be populated from the file

# Set this to a specific period ID (e.g., 1020) for testing with historical data.
# Set to None to automatically determine the period based on USE_PREVIOUS_PERIOD_ENV.
TEST_PERIOD = None # Change to a specific number (e.g., 1020) for testing, or None for dynamic period

# --- Environment Variable Checks for Period Logic and Message Customization ---
# If 'true', the script will use (current_period - 1). Otherwise, it uses current_period.
# This variable is set in the GitHub Actions workflow.
USE_PREVIOUS_PERIOD_ENV = os.getenv('USE_PREVIOUS_PERIOD', 'false').lower() == 'true'

# Determines the type of period being checked for message customization.
# Set in GitHub Actions workflow to 'current' or 'previous'.
PERIOD_TYPE = os.getenv('PERIOD_TYPE', 'current').lower() # Default to 'current'

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

# --- Function to Update Discord ID Mapping File ---
def update_discord_id_map_file(api_auth_header, map_file_path):
    """
    Fetches character names from WoW Audit API and updates the Discord ID map file.
    New characters are added with a null Discord ID.
    """
    print(f"Attempting to update Discord ID map file: {map_file_path}")
    characters_api_url = 'https://wowaudit.com/v1/characters'
    headers = {
        "accept": "application/json",
        "Authorization": api_auth_header
    }

    try:
        response = requests.get(characters_api_url, headers=headers)
        response.raise_for_status()
        api_characters_data = response.json()
        print(f"Successfully fetched {len(api_characters_data)} characters from WoW Audit API.")

        # Load existing map
        existing_map = {}
        if os.path.exists(map_file_path):
            with open(map_file_path, 'r', encoding='utf-8') as f:
                try:
                    existing_map = json.load(f)
                    print(f"Loaded existing Discord ID map with {len(existing_map)} entries.")
                except json.JSONDecodeError:
                    print(f"Warning: '{map_file_path}' is not a valid JSON file. Starting with an empty map.")
                    existing_map = {}
        else:
            print(f"'{map_file_path}' not found. A new map will be created.")

        updated_map = existing_map.copy()
        new_names_added = 0

        # Iterate through characters from API and add new ones to the map
        for char_data in api_characters_data:
            char_name = char_data.get('name')
            if char_name and char_name not in updated_map:
                updated_map[char_name] = None # Add new character with null Discord ID
                new_names_added += 1

        if new_names_added > 0:
            # Write the updated map back to the file
            with open(map_file_path, 'w', encoding='utf-8') as f:
                json.dump(updated_map, f, indent=2, ensure_ascii=False)
            print(f"Successfully added {new_names_added} new character(s) to '{map_file_path}'.")
            print("Remember to manually update the Discord IDs for new entries in this file.")
            return True # Indicate that the map was updated
        else:
            print("No new characters found to add to the Discord ID map.")
            return False # Indicate no update was needed

    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to fetch characters from WoW Audit API for map update: {e}")
        if e.response is not None:
            print(f"Response Content: {e.response.text}")
        return False
    except Exception as e:
        print(f"Error: An unexpected error occurred during map update: {e}")
        return False

# --- Main Script Logic ---
def main():
    global DISCORD_ID_MAP # Moved this declaration to the top of the function

    # Check if API_AUTHORIZATION_HEADER is set (from environment variable)
    if not API_AUTHORIZATION_HEADER:
        print("Error: WOWAUDIT_API_KEY environment variable is not set. Please configure it as a GitHub Secret.")
        exit(1) # Exit if API key is missing

    # Check if Discord Webhook URL is set
    if not DISCORD_WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL environment variable is not set. Please configure it as a GitHub Secret.")
        exit(1) # Exit if webhook URL is missing

    # Load Discord ID mapping if it's the current period report
    # And attempt to update the map file if it's the current period check
    if PERIOD_TYPE == 'current':
        map_updated = update_discord_id_map_file(API_AUTHORIZATION_HEADER, DISCORD_ID_MAP_FILE)
        
        try:
            with open(DISCORD_ID_MAP_FILE, 'r', encoding='utf-8') as f:
                # No 'global' keyword needed here as it's declared at function start
                DISCORD_ID_MAP = json.load(f)
            # print(f"DEBUG: Successfully loaded Discord ID map from {DISCORD_ID_MAP_FILE}") # Already printed in update function
        except FileNotFoundError:
            print(f"Warning: Discord ID map file '{DISCORD_ID_MAP_FILE}' not found after update attempt. Players will not be tagged.")
        except json.JSONDecodeError:
            print(f"Warning: Error decoding JSON from '{DISCORD_ID_MAP_FILE}' after update. Players will not be tagged.")
        except Exception as e:
            print(f"Warning: An unexpected error occurred while loading Discord ID map after update: {e}. Players will not be tagged.")
    else:
        # For previous period, just try to load the map without updating it
        try:
            with open(DISCORD_ID_MAP_FILE, 'r', encoding='utf-8') as f:
                # No 'global' keyword needed here as it's declared at function start
                DISCORD_ID_MAP = json.load(f)
            print(f"DEBUG: Successfully loaded Discord ID map from {DISCORD_ID_MAP_FILE} for non-current period.")
        except FileNotFoundError:
            print(f"Warning: Discord ID map file '{DISCORD_ID_MAP_FILE}' not found. Players will not be tagged.")
        except json.JSONDecodeError:
            print(f"Warning: Error decoding JSON from '{DISCORD_ID_MAP_FILE}'. Players will not be tagged.")
        except Exception as e:
            print(f"Warning: An unexpected error occurred while loading Discord ID map: {e}. Players will not be tagged.")


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

            if USE_PREVIOUS_PERIOD_ENV:
                period_to_use = current_period_from_api - 1
                print(f"Current period retrieved: {current_period_from_api}. Using PREVIOUS period for data: {period_to_use}")
            else:
                period_to_use = current_period_from_api
                print(f"Current period retrieved: {current_period_from_api}. Using CURRENT period for data: {period_to_use}")

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

            # Determine if the player needs to be reported and their status
            if dungeon_vault_option and \
               dungeon_vault_option.get("option_1") == REQUIRED_DUNGEON_OPTION_VALUE and \
               dungeon_vault_option.get("option_2") == REQUIRED_DUNGEON_OPTION_VALUE:
                # Player met the full requirement, do not report
                report_player = False
            else:
                # Player did NOT meet the full requirement, report them
                report_player = True

                if dungeon_vault_option and dungeon_vault_option.get("option_1") == REQUIRED_DUNGEON_OPTION_VALUE:
                    # Option 1 is met, but option 2 is not (or is None)
                    status_details = "Mangler 1 vault slot"
                else:
                    # Neither option 1 nor option 2 is met (or dungeons object missing/options are None)
                    status_details = "Mangler 2 vault slots"

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
                if isinstance(player['DungeonVaultStatus'], dict): # This branch is now less likely with new status_details
                    print(f"  Dungeons Options: Option 1: {player['DungeonVaultStatus']['Option1']}, Option 2: {player['DungeonVaultStatus']['Option2']}")
                else:
                    print(f"  Status: {player['DungeonVaultStatus']}")
                print("") # Add a blank line for readability
        else:
            print(f"All players in the data have at least one 'dungeons' vault option with both option_1 and option_2 set to {REQUIRED_DUNGEON_OPTION_VALUE}, or no data was processed.")

        # Step 4: Prepare and Send Discord Webhook Message (as an Embed)
        if DISCORD_WEBHOOK_URL: # Check if it's not empty/None
            # Customize embed title and initial description based on PERIOD_TYPE
            if PERIOD_TYPE == 'previous':
                embed_title = "M+ Requirement"
                initial_description = "Følgende spillere nåede ikke deres m+ mål i sidste uge:\n\n"
            else: # Default to 'current'
                embed_title = "M+ Requirement"
                initial_description = "Følgende spillere mangler forsat at klare deres m+ requirement inden reset:\n\n"

            embed_description = initial_description

            if players_to_report:
                for player in players_to_report:
                    player_name = player['PlayerName']
                    status = player['DungeonVaultStatus']
                    
                    # Attempt to get Discord ID for tagging, only for 'current' period
                    if PERIOD_TYPE == 'current' and player_name in DISCORD_ID_MAP and DISCORD_ID_MAP[player_name] is not None:
                        discord_id = DISCORD_ID_MAP[player_name]
                        embed_description += f"<@{discord_id}> - {status}\n"
                    else:
                        embed_description += f"{player_name} - {status}\n"
                        
                embed_color = 15548997 # Red color (decimal) for incomplete
            else:
                if PERIOD_TYPE == 'previous':
                    embed_description = "Alle spillere nåede deres m+ mål i sidste uge. Godt arbejde!"
                else: # Default to 'current'
                    embed_description = "Alle spillere har klaret deres m+ requirement inden reset. Godt arbejde!"
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

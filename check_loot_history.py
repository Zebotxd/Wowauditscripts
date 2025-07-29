import requests
import json
from datetime import datetime
import os
import gspread # Library for Google Sheets API interaction

# --- Configuration ---
API_AUTHORIZATION_HEADER = os.getenv('WOWAUDIT_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

DISCORD_ID_MAP_FILE = 'discord_id_map.json'
DISCORD_ID_MAP = {} # This will be populated from the file

# --- Google Sheets Configuration ---
# Your Google Sheet URL
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1s8OfqzI-GEmtmkhaHUzKQuO1HOZga-Z0ARNMqWE7NCw/edit?gid=0"
GOOGLE_SHEET_WORKSHEET_NAME = "Overview" # The name of the tab/worksheet
GOOGLE_SHEET_PLAYER_NAME_COLUMN = 1 # Column A (1-indexed)
GOOGLE_SHEET_TIER_PIECES_COLUMN = 23 # Column W (1-indexed)

# IMPORTANT: Google Sheets Service Account Credentials
# This should be stored as a GitHub Secret (e.g., GOOGLE_SHEETS_CREDENTIALS)
# The content of this secret should be the JSON key file for your Google Service Account.
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv('GOOGLE_SHEETS_CREDENTIALS')


# --- Class Emoji/Image Mapping (Copied from your existing script) ---
CLASS_IMAGE_MAP = {
    "Death Knight": {"emoji": "<:dk:1397596583801131069>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_deathknight.jpg", "abbr": "DK"},
    "Demon Hunter": {"emoji": "<:dh:1397596581678551082>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter.jpg", "abbr": "DH"},
    "Druid": {"emoji": "<:druid:1397596575210930216>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_druid.jpg", "abbr": "DRU"},
    "Evoker": {"emoji": "<:evoker:1397597387450749028>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker.jpg", "abbr": "EVO"},
    "Hunter": {"emoji": "<:hunter:1397596587399843981>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_hunter.jpg", "abbr": "HUN"},
    "Mage": {"emoji": "<:mage:1397596588922372169>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg", "abbr": "MAG"},
    "Monk": {"emoji": "<:monk:1397596577232584895>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_monk.jpg", "abbr": "MON"},
    "Paladin": {"emoji": "<:paladin:1397595736782409841>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_paladin.jpg", "abbr": "PAL"},
    "Priest": {"emoji": "<:priest:1397596592931868774>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_priest.jpg", "abbr": "PRI"},
    "Rogue": {"emoji": "<:rogue:1397596591027912797>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_rogue.jpg", "abbr": "ROG"},
    "Shaman": {"emoji": "<:shaman:1397596573453516981>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_shaman.jpg", "abbr": "SHA"},
    "Warlock": {"emoji": "<:warlock:1397596595423412314>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_warlock.jpg", "abbr": "WARL"},
    "Warrior": {"emoji": "<:warrior:1397596585054961696>", "url": "https://wow.zamimg.com/images/wow/icons/large/classicon_warrior.jpg", "abbr": "WARR"},
    "Unknown": {"emoji": "<:wussicat:1196785656777670656>", "url": "https://wow.zamimg.com/images/wow/icons/large/inv_misc_questionmark.jpg", "abbr": "?"} # Fallback
}

# --- Tier Piece Emoji Mapping ---
# Maps tier count to the FULL Discord emoji string.
# IMPORTANT: Ensure you have custom emojis with these exact IDs in your Discord server.
TIER_EMOJI_MAP = {
    0: "<:0_red:1399709199247872042>",
    1: "<:1_red:1399709201407934535>",
    2: "<:2_yellow:1399708873161703496>",
    3: "<:3_yellow:1399709204335296612>",
    4: "<:4_green:1399709206122070126>",
    # For 5, we need to decide which color to prioritize if both red/yellow/green are options
    # Based on your previous request, 5 should be green.
    5: "<:5_green:1399709207837671525>"
}
# Fallback emoji for N/A or unparseable tier data
TIER_EMOJI_FALLBACK = "<:gray_question:1196785656777670656>" # Using a generic question mark emoji ID


# --- Generic Thumbnail URLs for Report Status ---
THUMBNAIL_STATUS_ICONS = {
    "loot_report": "https://wow.zamimg.com/images/wow/icons/large/inv_misc_bag_07.jpg", # Generic bag/loot icon
    "no_loot": "https://wow.zamimg.com/images/wow/icons/large/inv_misc_empty_bag.jpg" # Empty bag icon
}


# --- Function to Send Message to Discord Webhook ---
def send_discord_webhook(message, webhook_url, embed_title="Loot History Report", embed_color=3447003, thumbnail_url=None):
    """
    Sends a message to a Discord webhook as an embed.
    """
    max_message_length = 4096

    if not message:
        print("Error: Discord embed description is empty. Not sending.")
        return

    if len(message) > max_message_length:
        print(f"Warning: Discord embed description exceeds {max_message_length} characters. It might be truncated or rejected.")

    embed = {
        "title": embed_title,
        "description": message,
        "color": embed_color,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}

    payload = {
        "embeds": [embed]
    }

    print(f"DEBUG: Attempting to send Discord embed. Embed title: {embed_title}")
    print(f"DEBUG: Webhook URL: {webhook_url}")
    print(f"DEBUG: JSON Payload (string): {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print("Discord webhook message (embed) sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to send Discord webhook message: {e}")
        if e.response is not None:
            print(f"Discord API Error Message: {e.response.text}")


# --- Function to Fetch Tier Data from Google Sheet ---
def fetch_tier_data_from_sheet(sheet_url, worksheet_name, player_col, tier_col, credentials_json):
    """
    Fetches player names and their tier piece counts from a Google Sheet.

    Args:
        sheet_url (str): The URL of the Google Sheet.
        worksheet_name (str): The name of the worksheet (tab).
        player_col (int): The 1-indexed column number for player names.
        tier_col (int): The 1-indexed column number for tier pieces (e.g., "4/5").
        credentials_json (str): JSON string of Google Service Account credentials.

    Returns:
        dict: A dictionary mapping player names to their tier piece strings (e.g., {"PlayerName": "4/5"}).
              Returns an empty dict if fetching fails.
    """
    tier_data = {}
    try:
        # Authenticate with Google Sheets using the service account credentials
        gc = gspread.service_account_from_dict(json.loads(credentials_json))
        
        # Open the spreadsheet by URL
        sh = gc.open_by_url(sheet_url)
        
        # Select the worksheet by name
        worksheet = sh.worksheet(worksheet_name)
        
        # Get all values from the player name column and tier pieces column
        # Using A1 notation to specify the range for better control and efficiency
        # Assuming data starts from row 1 (header row) and goes down
        # To get column A and W, we can fetch a range like A:W or A1:W[last_row]
        # For simplicity, let's fetch all values and process
        all_values = worksheet.get_all_values()
        
        # Skip header row if present (assuming first row is header)
        data_rows = all_values[1:] 
        
        for row in data_rows:
            if len(row) >= max(player_col, tier_col): # Ensure row has enough columns
                player_name = row[player_col - 1].strip() # Adjust to 0-indexed
                tier_piece_info = row[tier_col - 1].strip() # Adjust to 0-indexed
                
                if player_name: # Only add if player name is not empty
                    tier_data[player_name] = tier_piece_info
        
        print(f"Successfully fetched tier data for {len(tier_data)} players from Google Sheet.")
        return tier_data

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: Google Spreadsheet not found at URL: {sheet_url}")
    except gspread.exceptions.WorksheetNotFound:
        print(f"Error: Worksheet '{worksheet_name}' not found in the spreadsheet.")
    except json.JSONDecodeError:
        print("Error: GOOGLE_SHEETS_CREDENTIALS environment variable is not valid JSON.")
    except Exception as e:
        print(f"Error fetching data from Google Sheet: {e}")
    return {} # Return empty dict on failure


# --- Main Script Logic ---
def main():
    if not API_AUTHORIZATION_HEADER:
        print("Error: WOWAUDIT_API_KEY environment variable is not set. Please configure it as a GitHub Secret.")
        exit(1)

    if not DISCORD_WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL environment variable is not set. Please configure it as a GitHub Secret.")
        exit(1)

    # Load Discord ID map (for class info)
    try:
        with open(DISCORD_ID_MAP_FILE, 'r', encoding='utf-8') as f:
            global DISCORD_ID_MAP
            DISCORD_ID_MAP = json.load(f)
        print(f"DEBUG: Successfully loaded Discord ID map from {DISCORD_ID_MAP_FILE}.")
    except FileNotFoundError:
        print(f"Warning: Discord ID map file '{DISCORD_ID_MAP_FILE}' not found. Player classes may be missing.")
    except json.JSONDecodeError:
        print(f"Warning: Error decoding JSON from '{DISCORD_ID_MAP_FILE}'. Player classes may be missing.")
    except Exception as e:
        print(f"Warning: An unexpected error occurred while loading Discord ID map: {e}. Player classes may be missing.")

    # Fetch tier data from Google Sheet
    tier_pieces_data = {}
    if GOOGLE_SHEETS_CREDENTIALS_JSON:
        tier_pieces_data = fetch_tier_data_from_sheet(
            GOOGLE_SHEET_URL,
            GOOGLE_SHEET_WORKSHEET_NAME,
            GOOGLE_SHEET_PLAYER_NAME_COLUMN,
            GOOGLE_SHEET_TIER_PIECES_COLUMN,
            GOOGLE_SHEETS_CREDENTIALS_JSON
        )
        # --- DEBUGGING: Print fetched tier data ---
        print(f"DEBUG: Tier pieces data fetched from Google Sheet: {tier_pieces_data}")
        # --- END DEBUGGING ---
    else:
        print("Warning: GOOGLE_SHEETS_CREDENTIALS environment variable is not set. Skipping Google Sheet data fetch.")


    # Step 1: Get the current keystone_season_id
    print("Fetching current period to get keystone_season_id...")
    period_api_url = 'https://wowaudit.com/v1/period'
    headers = {
        "accept": "application/json",
        "Authorization": API_AUTHORIZATION_HEADER
    }
    
    current_season_id = None
    try:
        response = requests.get(period_api_url, headers=headers)
        response.raise_for_status()
        period_data = response.json()
        
        # Extract keystone_season_id from current_season
        current_season = period_data.get("current_season")
        if current_season and current_season.get("keystone_season_id"):
            current_season_id = current_season["keystone_season_id"]
            print(f"Retrieved keystone_season_id: {current_season_id}")
        else:
            raise ValueError("Could not find 'keystone_season_id' in the current_season data.")

    except requests.exceptions.RequestException as e:
        print(f"Error: An error occurred while fetching period data: {e}")
        if e.response is not None:
            print(f"Response Content: {e.response.text}")
        exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        exit(1)

    # Step 2: Get all characters to map IDs to names and classes
    print("Fetching all characters for name and class mapping...")
    characters_api_url = 'https://wowaudit.com/v1/characters'
    character_map = {} # Maps character_id to {"name": "CharName", "class": "Class"}
    try:
        response = requests.get(characters_api_url, headers=headers)
        response.raise_for_status()
        api_characters_data = response.json()
        print(f"Successfully fetched {len(api_characters_data)} characters.")
        for char_data in api_characters_data:
            char_id = char_data.get('id')
            char_name = char_data.get('name')
            char_class = char_data.get('class')
            if char_id and char_name:
                character_map[char_id] = {"name": char_name, "class": char_class}
    except requests.exceptions.RequestException as e:
        print(f"Error: An error occurred while fetching characters data: {e}")
        if e.response is not None:
            print(f"Response Content: {e.response.text}")
        exit(1)

    # Step 3: Get Loot History for the current season
    print(f"Fetching loot history for season ID: {current_season_id}...")
    loot_history_url = f"https://wowaudit.com/v1/loot_history/{current_season_id}"
    loot_counts = {} # Maps character_id to loot count

    try:
        response = requests.get(loot_history_url, headers=headers)
        response.raise_for_status()
        raw_loot_history_response = response.json() # Get the full JSON response
        
        # --- DEBUGGING: Print raw loot_history_response ---
        # print(f"DEBUG: Raw loot_history_response (full): {json.dumps(raw_loot_history_response, indent=2)}")
        # --- END DEBUGGING ---

        # Access the loot entries from the 'history_items' key
        loot_history_data = raw_loot_history_response.get('history_items', []) 
        
        print(f"Successfully fetched {len(loot_history_data)} loot entries (from 'history_items' key).")

        # Define excluded response types (added "transmog" for robustness)
        EXCLUDED_RESPONSE_TYPES = ["tmog", "transmorg", "transmog"]
        
        for loot_entry in loot_history_data:
            # Check if loot_entry is a dictionary before trying to use .get()
            if isinstance(loot_entry, dict):
                response_type_name = loot_entry.get('response_type', {}).get('name')
                is_discarded = loot_entry.get('discarded', False) # Default to False if 'discarded' is missing
                
                # Only count if response_type_name is NOT in the excluded list AND item is NOT discarded
                if (response_type_name and response_type_name.lower() not in EXCLUDED_RESPONSE_TYPES) and not is_discarded:
                    recipient_id = loot_entry.get('character_id') # Loot history uses 'character_id' for recipient
                    if recipient_id:
                        loot_counts[recipient_id] = loot_counts.get(recipient_id, 0) + 1
                else:
                    reason = []
                    if response_type_name and response_type_name.lower() in EXCLUDED_RESPONSE_TYPES:
                        reason.append(f"excluded response type '{response_type_name}'")
                    if is_discarded:
                        reason.append("item was discarded")
                    print(f"DEBUG: Skipping loot entry for item '{loot_entry.get('name')}' (ID: {loot_entry.get('id')}) because: {', '.join(reason)}")
            else:
                print(f"Warning: Unexpected loot entry format encountered. Expected dict, got {type(loot_entry)}: {loot_entry}")


    except requests.exceptions.RequestException as e:
        print(f"Error: An error occurred while fetching loot history: {e}")
        if e.response is not None:
            print(f"Response Content: {e.response.text}")
        exit(1)

    # Step 4: Prepare Report Data
    player_loot_data = []
    for char_id, char_info in character_map.items():
        player_name = char_info["name"]
        player_class = char_info["class"]
        loot_count = loot_counts.get(char_id, 0)
        
        # Get tier piece info from Google Sheet data
        tier_pieces_info = tier_pieces_data.get(player_name, "N/A") # Default to "N/A" if not found
        
        player_loot_data.append({
            "PlayerName": player_name,
            "Class": player_class,
            "LootCount": loot_count,
            "TierPieces": tier_pieces_info # Add tier pieces info
        })

    # Sort players by loot count ascending
    player_loot_data.sort(key=lambda x: x['LootCount'])

    print("\n--- Loot Report Data ---")
    if player_loot_data:
        for player in player_loot_data:
            print(f"Player: {player['PlayerName']} (Class: {player['Class']}) - Loot: {player['LootCount']} (Tier: {player['TierPieces']})")
    else:
        print("No player loot data found for this season.")

    # Step 5: Construct and Send Discord Embed
    embed_description = f"Lootfordeling for sæson {current_season_id} (sorteret efter færrest items):\n\n"
    embed_title = f"Loot Rapport: Sæson {current_season_id}"
    embed_color = 3447003 # Default Discord blue

    embed_thumbnail_url = THUMBNAIL_STATUS_ICONS['loot_report'] # Default loot bag icon

    if player_loot_data:
        for player in player_loot_data:
            player_name = player['PlayerName']
            loot_count = player['LootCount']
            tier_pieces = player['TierPieces'] # Get tier pieces info
            
            # Determine tier emoji and format the tier string
            formatted_tier_display = ""
            if tier_pieces != "N/A" and '/' in tier_pieces:
                try:
                    current_tier_str, max_tier_str = tier_pieces.split('/')
                    current_tier = int(current_tier_str)
                    max_tier = int(max_tier_str) # Get max tier number

                    # Get the color suffix based on current_tier
                    color_suffix = TIER_EMOJI_COLOR_SUFFIX_MAP.get(current_tier, "") # Default to empty if no mapping
                    
                    # Construct emojis for current_tier and max_tier using the determined color suffix
                    # Check if the emoji exists in TIER_EMOJI_MAP, otherwise fallback to text
                    current_tier_emoji_str = TIER_EMOJI_MAP.get(current_tier, current_tier_str)
                    max_tier_emoji_str = TIER_EMOJI_MAP.get(max_tier, max_tier_str) # Use max_tier to get its specific emoji if available, else text

                    # If the max_tier emoji is not found, but the current_tier has a color, apply that color to max_tier too
                    if not TIER_EMOJI_MAP.get(max_tier) and color_suffix:
                         max_tier_emoji_str = f":{max_tier}{color_suffix}:"
                    
                    formatted_tier_display = f"(Tier: {current_tier_emoji_str} / {max_tier_emoji_str})"
                except ValueError:
                    formatted_tier_display = f"(Tier: {TIER_EMOJI_FALLBACK} {tier_pieces})" # Fallback if parsing fails
            else:
                formatted_tier_display = f"(Tier: {TIER_EMOJI_FALLBACK} {tier_pieces})" # Default for N/A or invalid format
            
            # Get class display (emoji or abbr)
            player_data_from_map = DISCORD_ID_MAP.get(player_name, {})
            player_class = player_data_from_map.get('class', player['Class']) # Use class from character_map if not in discord_id_map
            
            class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['emoji']
            if not class_display:
                class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['abbr']
            
            # Format the player line with class emoji/abbr, loot count, and colored tier pieces
            embed_description += f"{class_display} {player_name} - {loot_count} items {formatted_tier_display}\n"
        
        # Set embed color based on some criteria if desired, e.g., if someone has 0 loot
        if any(p['LootCount'] == 0 for p in player_loot_data):
            embed_color = 15548997 # Red if someone has 0 loot
        else:
            embed_color = 3066993 # Green if everyone has loot
    else:
        embed_description = f"Ingen loot data fundet for sæson {current_season_id}."
        embed_thumbnail_url = THUMBNAIL_STATUS_ICONS['no_loot']
        embed_color = 808080 # Grey color for no data

    send_discord_webhook(embed_description, DISCORD_WEBHOOK_URL, embed_title, embed_color, thumbnail_url=embed_thumbnail_url)


if __name__ == "__main__":
    main()

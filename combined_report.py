import requests
import json
from datetime import datetime
import os
import gspread # Library for Google Sheets API interaction

# --- Configuration ---
API_AUTHORIZATION_HEADER = os.getenv('WOWAUDIT_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL_PREVIOUS_PERIOD') # Using previous period webhook for combined report

DISCORD_ID_MAP_FILE = 'discord_id_map.json'
DISCORD_ID_MAP = {} # This will be populated from the file

# --- Google Sheets Configuration ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1s8OfqzI-GEmtmkhaHUzKQuO1HOZga-Z0ARNMqWE7NCw/edit?gid=0"
GOOGLE_SHEET_WORKSHEET_NAME = "Overview"
GOOGLE_SHEET_PLAYER_NAME_COLUMN = 1 # Column A (1-indexed)
GOOGLE_SHEET_TIER_PIECES_COLUMN = 23 # Column W (1-indexed)
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv('GOOGLE_SHEETS_CREDENTIALS')

# --- M+ Requirement Configuration ---
REQUIRED_DUNGEON_OPTION_VALUE = 662

# --- Loot History Exclusion Configuration ---
EXCLUDED_LOOT_RESPONSE_TYPES = ["tmog", "transmorg", "transmog"]

# --- Class Emoji/Image Mapping ---
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
TIER_EMOJI_MAP = {
    0: "<:0_red:1399709199247872042>",
    1: "<:1_red:1399709201407934535>",
    2: "<:2_yellow:1399708873161703496>",
    3: "<:3_yellow:1399709204335296612>",
    4: "<:4_green:1399709206122070126>",
    5: "<:5_green:1399709207837671525>"
}
TIER_EMOJI_FALLBACK = "<:gray_question:1196785656777670656>"

# --- Generic Thumbnail URLs for Report Status ---
THUMBNAIL_STATUS_ICONS = {
    "mplus_incomplete": "https://wow.zamimg.com/images/wow/icons/large/inv_relics_hourglass.jpg", # Hourglass for incomplete M+
    "mplus_complete": "https://wow.zamimg.com/images/wow/icons/large/inv_misc_coin_01.jpg", # Coin for complete M+
    "loot_report": "https://wow.zamimg.com/images/wow/icons/large/inv_misc_bag_07.jpg", # Generic bag/loot icon
    "no_loot": "https://wow.zamimg.com/images/wow/icons/large/inv_misc_empty_bag.jpg" # Empty bag icon
}


# --- Function to Send Message to Discord Webhook ---
def send_discord_webhook(message, webhook_url, embed_title="Report", embed_color=3447003, thumbnail_url=None):
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


# --- Function to Update Discord ID Mapping File ---
def update_discord_id_map_file(api_auth_header, map_file_path):
    """
    Fetches character names and classes from WoW Audit API and updates the Discord ID map file.
    New characters are added with a null Discord ID and their class.
    Existing entries are updated with class info if missing or different, and converted to new format if old.
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
        changes_made = False

        # Iterate through characters from API and update the map
        for char_data in api_characters_data:
            char_name = char_data.get('name')
            char_class = char_data.get('class') # Get the class from the API response

            if not char_name:
                continue # Skip if no name

            if char_name not in updated_map:
                # New character: add with null discord_id and fetched class
                updated_map[char_name] = {"discord_id": None, "class": char_class}
                print(f"Added new character '{char_name}' (Class: {char_class}) to map.")
                changes_made = True
            else:
                # Existing character: check format and update class if needed
                current_entry = updated_map[char_name]
                if isinstance(current_entry, str):
                    # Old format (just Discord ID string), convert to new dict format
                    updated_map[char_name] = {"discord_id": current_entry, "class": char_class}
                    print(f"Converted '{char_name}' to new map format, added Class: {char_class}.")
                    changes_made = True
                elif isinstance(current_entry, dict):
                    # New format, check if class needs update
                    if current_entry.get("class") != char_class:
                        updated_map[char_name]["class"] = char_class
                        print(f"Updated class for '{char_name}' to: {char_class}.")
                        changes_made = True
                    # If discord_id is missing but class is present, ensure discord_id is None
                    if "discord_id" not in current_entry:
                        updated_map[char_name]["discord_id"] = None
                        changes_made = True
                else:
                    print(f"Warning: Unexpected format for '{char_name}' in map. Skipping class update.")


        if changes_made:
            # Write the updated map back to the file
            with open(map_file_path, 'w', encoding='utf-8') as f:
                json.dump(updated_map, f, indent=2, ensure_ascii=False)
            print(f"Discord ID map '{map_file_path}' updated successfully.")
            print("Remember to manually update the 'discord_id' for new/updated entries in this file.")
            return True # Indicate that the map was updated
        else:
            print("No changes needed for the Discord ID map.")
            return False # Indicate no update was needed

    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to fetch characters from WoW Audit API for map update: {e}")
        if e.response is not None:
            print(f"Response Content: {e.response.text}")
        return False
    except Exception as e:
        print(f"Error: An unexpected error occurred during map update: {e}")
        return False

# --- Function to Fetch Tier Data from Google Sheet ---
def fetch_tier_data_from_sheet(sheet_url, worksheet_name, player_col, tier_col, credentials_json):
    """
    Fetches player names and their tier piece counts from a Google Sheet.
    """
    tier_data = {}
    if not credentials_json:
        print("Warning: GOOGLE_SHEETS_CREDENTIALS environment variable is not set. Skipping Google Sheet data fetch.")
        return {}

    try:
        gc = gspread.service_account_from_dict(json.loads(credentials_json))
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.worksheet(worksheet_name)
        all_values = worksheet.get_all_values()
        
        data_rows = all_values[1:] # Skip header row
        
        for row in data_rows:
            if len(row) >= max(player_col, tier_col):
                player_name = row[player_col - 1].strip()
                tier_piece_info = row[tier_col - 1].strip()
                
                if player_name:
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
    return {}


# --- Main Script Logic ---
def main():
    global DISCORD_ID_MAP

    if not API_AUTHORIZATION_HEADER:
        print("Error: WOWAUDIT_API_KEY environment variable is not set. Please configure it as a GitHub Secret.")
        exit(1)
    if not DISCORD_WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL environment variable is not set. Please configure it as a GitHub Secret.")
        exit(1)

    # Update and load Discord ID map
    update_discord_id_map_file(API_AUTHORIZATION_HEADER, DISCORD_ID_MAP_FILE)
    try:
        with open(DISCORD_ID_MAP_FILE, 'r', encoding='utf-8') as f:
            DISCORD_ID_MAP = json.load(f)
    except Exception as e:
        print(f"Error loading Discord ID map after update attempt: {e}. Player classes/tags may be missing.")

    # Fetch tier data from Google Sheet
    tier_pieces_data = fetch_tier_data_from_sheet(
        GOOGLE_SHEET_URL,
        GOOGLE_SHEET_WORKSHEET_NAME,
        GOOGLE_SHEET_PLAYER_NAME_COLUMN,
        GOOGLE_SHEET_TIER_PIECES_COLUMN,
        GOOGLE_SHEETS_CREDENTIALS_JSON
    )
    print(f"DEBUG: Tier pieces data fetched from Google Sheet: {tier_pieces_data}")


    # --- Fetch current period and season ID ---
    print("Fetching current period to get keystone_season_id...")
    period_api_url = 'https://wowaudit.com/v1/period'
    headers = {"accept": "application/json", "Authorization": API_AUTHORIZATION_HEADER}
    
    current_period_from_api = None
    current_season_id = None
    try:
        response = requests.get(period_api_url, headers=headers)
        response.raise_for_status()
        period_data = response.json()
        
        current_period_from_api = period_data.get("current_period")
        current_season = period_data.get("current_season")
        if current_season and current_season.get("keystone_season_id"):
            current_season_id = current_season["keystone_season_id"]
            print(f"Retrieved current_period: {current_period_from_api}, keystone_season_id: {current_season_id}")
        else:
            raise ValueError("Could not find 'keystone_season_id' in the current_season data.")

    except requests.exceptions.RequestException as e:
        print(f"Error: An error occurred while fetching period data: {e}")
        exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        exit(1)

    # --- M+ Requirement Check (Previous Period) ---
    mplus_report_period = current_period_from_api - 1
    print(f"\n--- Running M+ Requirement Check for period: {mplus_report_period} ---")
    mplus_historical_data_url = f"https://wowaudit.com/v1/historical_data?period={mplus_report_period}"
    
    mplus_players_to_report = []
    try:
        response = requests.get(mplus_historical_data_url, headers=headers)
        response.raise_for_status()
        mplus_raw_data = response.json()
        mplus_data_items = mplus_raw_data.get('characters', [])

        for item in mplus_data_items:
            # Safely check if item is a dictionary before proceeding
            if not isinstance(item, dict):
                print(f"Warning: M+ data item is not a dictionary. Skipping: {item}")
                continue

            # Safely get nested dictionaries, providing empty dict as default
            data_content = item.get("data", {})
            vault_options_content = data_content.get("vault_options", {})
            dungeon_vault_option = vault_options_content.get("dungeons")

            name = item.get("name") # Get name after ensuring item is a dict

            report_player = True
            status_details = None

            if dungeon_vault_option and \
               dungeon_vault_option.get("option_1") == REQUIRED_DUNGEON_OPTION_VALUE and \
               dungeon_vault_option.get("option_2") == REQUIRED_DUNGEON_OPTION_VALUE:
                report_player = False
            else:
                if dungeon_vault_option and dungeon_vault_option.get("option_1") == REQUIRED_DUNGEON_OPTION_VALUE:
                    status_details = "Mangler 1 vault slot"
                else:
                    status_details = "Mangler 2 vault slots"

            if report_player:
                mplus_players_to_report.append({"PlayerName": name, "DungeonVaultStatus": status_details})
        
        print(f"DEBUG: M+ report found {len(mplus_players_to_report)} players missing requirements.")

    except requests.exceptions.RequestException as e:
        print(f"Error: M+ report - An error occurred fetching historical data: {e}")
        mplus_players_to_report = [] # Ensure it's empty on error

    mplus_embed_description_part = "Følgende spillere nåede ikke deres m+ mål i sidste uge:\n\n"
    mplus_embed_color = 3066993 # Green default
    mplus_thumbnail_url = THUMBNAIL_STATUS_ICONS['mplus_complete']

    if mplus_players_to_report:
        mplus_embed_description_part = ":warning:Følgende spillere nåede ikke deres m+ mål i sidste uge:\n\n"
        # Separate players by slot requirement for M+ report
        players_two_slots = [p for p in mplus_players_to_report if p['DungeonVaultStatus'] == "Mangler 2 vault slots"]
        players_one_slot = [p for p in mplus_players_to_report if p['DungeonVaultStatus'] == "Mangler 1 vault slot"]

        if players_two_slots:
            mplus_embed_description_part += ":red_circle: **Mangler 2 vault slots:**\n\n"
            for player in players_two_slots:
                player_name = player['PlayerName']
                player_data_from_map = DISCORD_ID_MAP.get(player_name, {})
                player_class = player_data_from_map.get('class', 'Unknown')
                class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['emoji']
                if not class_display:
                    class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['abbr']
                discord_id = player_data_from_map.get('discord_id')
                mplus_embed_description_part += f"{class_display} <@{discord_id}>\n" if discord_id else f"{class_display} {player_name}\n"
        
        if players_one_slot:
            if players_two_slots:
                mplus_embed_description_part += "\n"
            mplus_embed_description_part += ":yellow_circle: **Mangler kun 1 vault slot:**\n\n"
            for player in players_one_slot:
                player_name = player['PlayerName']
                player_data_from_map = DISCORD_ID_MAP.get(player_name, {})
                player_class = player_data_from_map.get('class', 'Unknown')
                class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['emoji']
                if not class_display:
                    class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['abbr']
                discord_id = player_data_from_map.get('discord_id')
                mplus_embed_description_part += f"{class_display} <@{discord_id}>\n" if discord_id else f"{class_display} {player_name}\n"
        
        mplus_embed_color = 15548997 # Red for incomplete
        mplus_thumbnail_url = THUMBNAIL_STATUS_ICONS['mplus_incomplete']
    else:
        mplus_embed_description_part = "Alle spillere nåede deres m+ mål i sidste uge. Godt arbejde!"
        mplus_embed_color = 3066993 # Green for complete
        mplus_thumbnail_url = THUMBNAIL_STATUS_ICONS['mplus_complete']


    # --- Loot History Report ---
    print(f"\n--- Running Loot History Report for season ID: {current_season_id} ---")
    loot_history_url = f"https://wowaudit.com/v1/loot_history/{current_season_id}"
    loot_counts = {}
    player_loot_data = [] # To store combined player info and loot count

    try:
        response = requests.get(loot_history_url, headers=headers)
        response.raise_for_status()
        raw_loot_history_response = response.json()
        loot_history_data = raw_loot_history_response.get('history_items', [])
        
        for loot_entry in loot_history_data:
            if isinstance(loot_entry, dict):
                response_type_name = loot_entry.get('response_type', {}).get('name')
                is_discarded = loot_entry.get('discarded', False)
                
                if (response_type_name and response_type_name.lower() not in EXCLUDED_LOOT_RESPONSE_TYPES) and not is_discarded:
                    recipient_id = loot_entry.get('character_id')
                    if recipient_id:
                        loot_counts[recipient_id] = loot_counts.get(recipient_id, 0) + 1
                else:
                    reason = []
                    if response_type_name and response_type_name.lower() in EXCLUDED_LOOT_RESPONSE_TYPES:
                        reason.append(f"excluded response type '{response_type_name}'")
                    if is_discarded:
                        reason.append("item was discarded")
                    print(f"DEBUG: Skipping loot entry for item '{loot_entry.get('name')}' (ID: {loot_entry.get('id')}) because: {', '.join(reason)}")
            else:
                print(f"Warning: Unexpected loot entry format encountered. Expected dict, got {type(loot_entry)}: {loot_entry}")

        # Combine character_map with loot_counts and tier_pieces_data
        for char_id, char_info in character_map.items():
            player_name = char_info["name"]
            player_class = char_info["class"]
            loot_count = loot_counts.get(char_id, 0)
            tier_pieces_info = tier_pieces_data.get(player_name, "N/A")
            
            player_loot_data.append({
                "PlayerName": player_name,
                "Class": player_class,
                "LootCount": loot_count,
                "TierPieces": tier_pieces_info
            })
        
        player_loot_data.sort(key=lambda x: x['LootCount']) # Sort by loot count

    except requests.exceptions.RequestException as e:
        print(f"Error: Loot report - An error occurred fetching loot history: {e}")
        player_loot_data = [] # Ensure it's empty on error

    loot_embed_description_part = "\n\n---\n\n**Lootfordeling for denne sæson (sorteret efter færrest items):**\n\n"
    loot_embed_color = 3447003 # Default Discord blue

    if player_loot_data:
        for player in player_loot_data:
            player_name = player['PlayerName']
            loot_count = player['LootCount']
            tier_pieces = player['TierPieces']
            
            formatted_tier_display = ""
            if tier_pieces != "N/A" and '/' in tier_pieces:
                try:
                    current_tier_str, max_tier_str = tier_pieces.split('/')
                    current_tier = int(current_tier_str)
                    max_tier = int(max_tier_str)

                    # Get the emoji for current_tier, fallback to string if not found
                    current_tier_emoji = TIER_EMOJI_MAP.get(current_tier, current_tier_str)
                    
                    # Get the emoji for max_tier, fallback to string if not found
                    # Use the same color logic for max_tier as current_tier
                    max_tier_emoji = TIER_EMOJI_MAP.get(max_tier, max_tier_str)
                    
                    formatted_tier_display = f"(Tier: {current_tier_emoji} / {max_tier_emoji})"
                except ValueError:
                    formatted_tier_display = f"(Tier: {TIER_EMOJI_FALLBACK} {tier_pieces})"
            else:
                formatted_tier_display = f"(Tier: {TIER_EMOJI_FALLBACK} {tier_pieces})"
            
            player_data_from_map = DISCORD_ID_MAP.get(player_name, {})
            player_class = player_data_from_map.get('class', player['Class'])
            class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['emoji']
            if not class_display:
                class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['abbr']
            
            loot_embed_description_part += f"{class_display} {player_name} - {loot_count} items {formatted_tier_display}\n"
        
        if any(p['LootCount'] == 0 for p in player_loot_data):
            loot_embed_color = 15548997 # Red if someone has 0 loot
        else:
            loot_embed_color = 3066993 # Green if everyone has loot
    else:
        loot_embed_description_part += f"Ingen loot data fundet for sæson {current_season_id}."
        loot_embed_color = 808080 # Grey color for no data


    # --- Final Combined Discord Embed ---
    final_embed_description = mplus_embed_description_part + loot_embed_description_part
    final_embed_title = "Ugentlig Rapport"
    final_embed_color = mplus_embed_color # Prioritize M+ status for overall color
    final_thumbnail_url = mplus_thumbnail_url # Prioritize M+ status for overall thumbnail

    # If M+ is complete but loot has issues, adjust color/thumbnail
    if not mplus_players_to_report and any(p['LootCount'] == 0 for p in player_loot_data):
        final_embed_color = loot_embed_color # Use loot color if M+ is green but loot is red
        final_thumbnail_url = THUMBNAIL_STATUS_ICONS['loot_report'] # Use loot icon if loot is the issue

    send_discord_webhook(
        final_embed_description,
        DISCORD_WEBHOOK_URL,
        embed_title=final_embed_title,
        embed_color=final_embed_color,
        thumbnail_url=final_thumbnail_url
    )


if __name__ == "__main__":
    main()

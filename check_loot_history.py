import requests
import json
from datetime import datetime
import os

# --- Configuration ---
API_AUTHORIZATION_HEADER = os.getenv('WOWAUDIT_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

DISCORD_ID_MAP_FILE = 'discord_id_map.json'
DISCORD_ID_MAP = {} # This will be populated from the file

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


# --- Main Script Logic ---
def main():
    if not API_AUTHORIZATION_HEADER:
        print("Error: WOWAUDIT_API_KEY environment variable is not set. Please configure it as a GitHub Secret.")
        exit(1)

    if not DISCORD_WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL environment variable is not set. Please configure it as a GitHub Secret.")
        exit(1)

    # Load Discord ID mapping (for class info and tagging)
    try:
        with open(DISCORD_ID_MAP_FILE, 'r', encoding='utf-8') as f:
            global DISCORD_ID_MAP
            DISCORD_ID_MAP = json.load(f)
        print(f"DEBUG: Successfully loaded Discord ID map from {DISCORD_ID_MAP_FILE}.")
    except FileNotFoundError:
        print(f"Warning: Discord ID map file '{DISCORD_ID_MAP_FILE}' not found. Player classes and tags may be missing.")
    except json.JSONDecodeError:
        print(f"Warning: Error decoding JSON from '{DISCORD_ID_MAP_FILE}'. Player classes and tags may be missing.")
    except Exception as e:
        print(f"Warning: An unexpected error occurred while loading Discord ID map: {e}. Player classes and tags may be missing.")

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
        loot_history_data = response.json()
        print(f"Successfully fetched {len(loot_history_data)} loot entries.")

        for loot_entry in loot_history_data:
            # Check if loot_entry is a dictionary before trying to use .get()
            if isinstance(loot_entry, dict):
                recipient_id = loot_entry.get('recipient_character_id')
                if recipient_id:
                    loot_counts[recipient_id] = loot_counts.get(recipient_id, 0) + 1
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
        
        player_loot_data.append({
            "PlayerName": player_name,
            "Class": player_class,
            "LootCount": loot_count
        })

    # Sort players by loot count ascending
    player_loot_data.sort(key=lambda x: x['LootCount'])

    print("\n--- Loot Report Data ---")
    if player_loot_data:
        for player in player_loot_data:
            print(f"Player: {player['PlayerName']} (Class: {player['Class']}) - Loot: {player['LootCount']}")
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
            
            player_data_from_map = DISCORD_ID_MAP.get(player_name, {})
            player_class = player_data_from_map.get('class', player['Class']) # Use class from character_map if not in discord_id_map
            
            class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['emoji']
            if not class_display:
                class_display = CLASS_IMAGE_MAP.get(player_class, CLASS_IMAGE_MAP['Unknown'])['abbr']
            
            discord_id = player_data_from_map.get('discord_id')

            if discord_id is not None:
                embed_description += f"{class_display} <@{discord_id}> - {loot_count} items\n"
            else:
                embed_description += f"{class_display} {player_name} - {loot_count} items\n"
        
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

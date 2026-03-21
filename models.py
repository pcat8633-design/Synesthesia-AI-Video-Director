import os
import csv
import json
import re
import time
import glob
import shutil
import threading

import requests
import pandas as pd

import config
from utils import get_file_path

# ==========================================
# LLM BRIDGE
# ==========================================

class LLMBridge:
    def __init__(self, base_url=None):
        self.base_url = base_url if base_url is not None else config.LM_STUDIO_URL

    def get_models(self):
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m['id'] for m in data['data']]
        except Exception:
            pass
        return ["qwen3-vl-8b-instruct-abliterated-v2.0"]

    def query(self, system_prompt, user_prompt, model, temperature=0.7):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature
        }
        try:
            resp = requests.post(url, json=payload, timeout=600)
            if resp.status_code != 200:
                return f"Error {resp.status_code} from LLM: {resp.text}"
            return resp.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f"Error: {str(e)}"

# ==========================================
# PROJECT MANAGER
# ==========================================

class ProjectManager:
    def __init__(self):
        self.current_project = None
        self.base_dir = "projects"
        os.makedirs(self.base_dir, exist_ok=True)
        self.df = pd.DataFrame(columns=config.REQUIRED_COLUMNS)
        self.stop_generation = False
        self.stop_video_generation = False
        self.is_generating = False
        self.llm_busy = False
        self.character_bibles = {}  # {character_name: description}

        # Render Queue
        self.render_queue = []
        self.queue_lock = threading.Lock()
        self.queue_paused = False
        self.queue_processor_running = False

        # Time Tracking Variables
        self.total_time_spent = 0
        self.session_start_time = None

        # GPU / RAM leakage warning (set by Tab 3 after each render)
        self.ltx_ram_warning = ""

    def __deepcopy__(self, memo):
        import copy
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if isinstance(v, type(threading.Lock())):
                setattr(result, k, threading.Lock())
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result

    def sanitize_name(self, name):
        return re.sub(r'[\\/*?:"<>|]', "", name).strip().strip(".").replace(" ", "_")

    def get_current_total_time(self):
        if self.session_start_time and self.current_project:
            elapsed = time.time() - self.session_start_time
            self.session_start_time = time.time()
            self.total_time_spent += elapsed

            settings = self.load_project_settings()
            settings["total_time_spent"] = self.total_time_spent
            path = os.path.join(self.base_dir, self.current_project, "settings.json")
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=4)
            except Exception:
                pass

        return self.total_time_spent

    def create_project(self, name):
        if not name: return "Invalid name"
        clean_name = self.sanitize_name(name)
        path = os.path.join(self.base_dir, clean_name)

        folders = ["assets", "audio_chunks", "videos", "renders", "cutting_room", "first_frames"]

        if os.path.exists(path):
            return f"Project '{clean_name}' already exists."

        for f in folders:
            os.makedirs(os.path.join(path, f), exist_ok=True)

        self.df = pd.DataFrame(columns=config.REQUIRED_COLUMNS)
        self.df.to_csv(os.path.join(path, "shot_list.csv"), index=False)
        self.current_project = clean_name

        self.total_time_spent = 0
        self.session_start_time = time.time()

        with open(os.path.join(path, "lyrics.txt"), "w") as f:
            f.write("")
        return f"Project '{clean_name}' created."

    def load_project(self, name):
        path = os.path.join(self.base_dir, name)
        csv_path = os.path.join(path, "shot_list.csv")
        if os.path.exists(csv_path):
            self.df = pd.read_csv(csv_path)
            for col in config.REQUIRED_COLUMNS:
                if col not in self.df.columns:
                    self.df[col] = ""
            self.current_project = name

            settings = self.load_project_settings()
            self.total_time_spent = settings.get("total_time_spent", 0)
            self.session_start_time = time.time()

            sync_video_directory(self)
            self.load_character_bibles()
            return f"Loaded '{name}'", self.df
        return "Project not found.", pd.DataFrame()

    def import_csv(self, file_obj):
        if not self.current_project:
            return "No project loaded.", self.df

        try:
            new_df = pd.read_csv(get_file_path(file_obj))

            if "Shot_ID" not in new_df.columns:
                return "❌ Error: Uploaded CSV is missing the 'Shot_ID' column.", self.df

            if len(new_df) != len(self.df):
                return f"❌ Error: Uploaded CSV has {len(new_df)} rows, but current project has {len(self.df)} rows.", self.df

            new_df = new_df.set_index("Shot_ID")
            curr_df = self.df.set_index("Shot_ID")

            missing_shots = set(curr_df.index) - set(new_df.index)
            if missing_shots:
                return f"❌ Error: CSV is missing required Shot IDs: {', '.join(str(s) for s in missing_shots)}", self.df

            if 'Type' not in new_df.columns:
                return "❌ Error: CSV is missing 'Type' column.", self.df

            valid_types = {"Vocal", "Action"}
            invalid_types = set(new_df['Type'].unique()) - valid_types
            if invalid_types:
                return f"❌ Error: Invalid Type values: {', '.join(map(str, invalid_types))}. Must be 'Vocal' or 'Action'.", self.df

            type_changed = new_df['Type'] != curr_df['Type']
            changed_shots = curr_df[type_changed].index.tolist()

            if type_changed.any():
                curr_df['Type'] = new_df['Type']

            if 'Video_Prompt' in new_df.columns:
                curr_df['Video_Prompt'] = new_df['Video_Prompt']
                self.df = curr_df.reset_index()
                self.save_data()
                if changed_shots:
                    return f"✅ CSV imported. Type changed for: {', '.join(map(str, changed_shots))}. Prompts updated.", self.df
                return "✅ CSV Uploaded & Verified. Prompts successfully updated.", self.df
            else:
                if changed_shots:
                    self.df = curr_df.reset_index()
                    self.save_data()
                    return f"✅ Type changed for: {', '.join(map(str, changed_shots))}.", self.df
                return "❌ Error: 'Video_Prompt' column not found in uploaded CSV.", self.df

        except Exception as e:
            return f"❌ Error reading CSV: {e}", self.df

    def export_csv(self):
        if not self.current_project or self.df.empty:
            return None
        return os.path.join(self.base_dir, self.current_project, "shot_list.csv")

    def save_data(self):
        if self.current_project:
            path = os.path.join(self.base_dir, self.current_project, "shot_list.csv")
            self.df.to_csv(path, index=False)

    def save_character_bibles(self):
        if not self.current_project:
            return
        path = os.path.join(self.base_dir, self.current_project, "character_bibles.csv")
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                writer.writerow(["character_name", "description"])
                for name, desc in self.character_bibles.items():
                    writer.writerow([name, desc])
        except Exception as e:
            print(f"Error saving character bibles: {e}")

    def load_character_bibles(self):
        if not self.current_project:
            self.character_bibles = {}
            return {}
        path = os.path.join(self.base_dir, self.current_project, "character_bibles.csv")
        bibles = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)  # skip header
                    for row in reader:
                        if len(row) >= 2 and row[0].strip():
                            bibles[row[0].strip()] = row[1].strip()
            except Exception as e:
                print(f"Error loading character bibles: {e}")
        self.character_bibles = bibles
        return bibles

    def update_characters_column(self):
        """Scan each shot's Video_Prompt and record which bible characters appear in it."""
        if "Characters" not in self.df.columns:
            self.df["Characters"] = ""
        for idx, row in self.df.iterrows():
            prompt_raw = row.get("Video_Prompt", "")
            prompt = "" if pd.isna(prompt_raw) else str(prompt_raw)
            found = []
            for name in self.character_bibles:
                pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE | re.UNICODE)
                if pattern.search(prompt):
                    found.append(name)
            self.df.at[idx, "Characters"] = ", ".join(found)

    def get_path(self, subfolder):
        if not self.current_project: return None
        return os.path.join(self.base_dir, self.current_project, subfolder)

    def save_lyrics(self, text):
        if not self.current_project: return
        path = os.path.join(self.base_dir, self.current_project, "lyrics.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def get_lyrics(self):
        if not self.current_project: return ""
        path = os.path.join(self.base_dir, self.current_project, "lyrics.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def save_project_settings(self, settings_dict):
        if not self.current_project: return "No project loaded."

        existing_settings = self.load_project_settings()
        existing_settings.update(settings_dict)
        existing_settings["total_time_spent"] = self.get_current_total_time()

        path = os.path.join(self.base_dir, self.current_project, "settings.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(existing_settings, f, indent=4)
            return f"Settings saved."
        except Exception as e:
            return f"Error saving settings: {e}"

    def load_project_settings(self):
        if not self.current_project: return {}
        path = os.path.join(self.base_dir, self.current_project, "settings.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_asset(self, source_path, filename):
        if not self.current_project or not source_path: return None
        dest = os.path.join(self.get_path("assets"), filename)
        if os.path.abspath(source_path) == os.path.abspath(dest): return dest
        shutil.copy(source_path, dest)
        return dest

    def get_asset_path_if_exists(self, filename):
        if not self.current_project: return None
        path = os.path.join(self.get_path("assets"), filename)
        return path if os.path.exists(path) else None

# ==========================================
# LOGIC: DIRECTORY SYNC
# ==========================================

def sync_video_directory(pm):
    if not pm.current_project: return "No project loaded."
    vid_dir = pm.get_path("videos")
    if not os.path.exists(vid_dir): return "No videos directory."

    mp4s = glob.glob(os.path.join(vid_dir, "*.mp4"))
    shot_vids = {}

    for v in mp4s:
        fname = os.path.basename(v)
        shot_id = fname.split("_")[0].upper()
        if shot_id not in shot_vids: shot_vids[shot_id] = []
        shot_vids[shot_id].append(v)

    if "All_Video_Paths" not in pm.df.columns:
        pm.df["All_Video_Paths"] = ""

    for idx, row in pm.df.iterrows():
        sid = str(row.get("Shot_ID", "")).upper()
        if sid in shot_vids:
            vids = sorted(shot_vids[sid], key=os.path.getmtime, reverse=True)
            pm.df.at[idx, "All_Video_Paths"] = ",".join(vids)

            curr_path_raw = row.get("Video_Path", "")
            curr_path = "" if pd.isna(curr_path_raw) else str(curr_path_raw)

            if not curr_path or not os.path.exists(curr_path) or curr_path not in vids:
                pm.df.at[idx, "Video_Path"] = vids[0]
                pm.df.at[idx, "Status"] = "Done"
        else:
            pm.df.at[idx, "All_Video_Paths"] = ""

            curr_path_raw = row.get("Video_Path", "")
            curr_path = "" if pd.isna(curr_path_raw) else str(curr_path_raw)

            if not curr_path or not os.path.exists(curr_path):
                pm.df.at[idx, "Video_Path"] = ""
                pm.df.at[idx, "Status"] = "Pending"

    pm.save_data()
    return "Directory sync complete."

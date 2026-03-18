import os
import json
import re
import glob

# ==========================================
# CONFIGURATION
# ==========================================
LTX_BASE_URL = "http://127.0.0.1:8000/api"
LM_STUDIO_URL = "http://127.0.0.1:1234/v1"
VIDEO_BACKEND = "LTX Desktop"  # "LTX Desktop" | "Wan2GP"

REQUIRED_COLUMNS = [
    "Shot_ID", "Type",
    "Start_Time", "End_Time", "Duration",
    "Start_Frame", "End_Frame", "Total_Frames",
    "Lyrics", "Video_Prompt", "Video_Path", "All_Video_Paths", "Status"
]

RESOLUTION_MAP = {
    "540p": (960, 540),
    "720p": (1280, 720),
    "1080p": (1920, 1080)
}

DEFAULT_NEGATIVE_PROMPT = "blurry, distorted, low quality, artifacts, watermark"

def load_styles():
    styles_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.json")
    try:
        with open(styles_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

STYLES = load_styles()
STYLE_NAMES = ["None"] + [s["name"] for s in STYLES]

def style_to_slug(style_name):
    """Convert a style display name to a filename-safe slug.
    'LTX - Claymation' → 'claymation', 'LTX - Film Noir' → 'film_noir'"""
    if not style_name or style_name == "None":
        return None
    name = re.sub(r'^LTX\s*-\s*', '', style_name, flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

def slug_to_style_name(slug):
    """Reverse lookup slug → display name. Falls back to slug if not found."""
    for s in STYLES:
        if style_to_slug(s["name"]) == slug:
            return s["name"]
    return slug

def slug_from_filename(fname):
    """Extract style slug from a video filename, or None if unstyled.
    'S001_vid_claymation_v1726524982.mp4' → 'claymation'
    'S001_vid_v1726524982.mp4' → None
    """
    match = re.match(r'^[^_]+_vid_(.+)_v\d+\.mp4$', fname)
    return match.group(1) if match else None

def get_styles_in_videos_dir(pm):
    """Scan the videos/ dir and return sorted list of style display names present."""
    vid_dir = pm.get_path("videos")
    if not vid_dir or not os.path.exists(vid_dir):
        return []
    slugs = set()
    for f in glob.glob(os.path.join(vid_dir, "*.mp4")):
        slug = slug_from_filename(os.path.basename(f))
        if slug:
            slugs.add(slug)
    return sorted([slug_to_style_name(s) for s in slugs])

DEFAULT_CONCEPT_PROMPT = (
    "Context: The overarching plot is: {plot}\n"
    "Previous Shot Visual: {prev_shot}\n"
    "Current Shot Info: Timestamp {start}s, Duration {duration}s, Type: {type}.\n"
    "Task: Write a highly detailed visual description for this video shot encompassing the action. "
    "Describe the scene, camera motion, emotions, lighting and performance only. "
    "Pay special attention to the camera's motion. Do not include any additional notes or titles."
)

LTX_SYSTEM_PROMPT = """You are an expert cinematography AI director writing video generation prompts. Adhere strictly to these rules:

1. Establish the shot: Use cinematography terms that match the preferred film genre. Include aspects like scale or specific category characteristics.
2. Set the scene: Describe lighting conditions, color palette, surface textures, and atmosphere to shape the mood.
3. Describe the action: Write the core action as a natural sequence, flowing from beginning to end.
4. Define your character(s): Include age, hairstyle, clothing, and distinguishing details. Express emotions through physical cues.
5. Identify camera movement(s): Specify when the view should shift and how. Include how subjects or objects appear after the camera motion.
6. Format: Keep your prompt in a SINGLE flowing paragraph.
7. Grammar: Use present tense verbs to describe movement and action.
8. Detail scale: Match your detail to the shot scale (Closeups need more precise detail than wide shots).
9. Camera focus: When describing camera movement, focus on the camera's relationship to the subject.
10. Length: Write 4 to 8 descriptive sentences to cover all key aspects."""

SCRIPTED_PROMPT_TEMPLATE = """Create a short narrative film via AI video prompts while adhering to the following main character, gender, settings, and rough concept.  See also the following csv shot list with durations and frame counts.  Return the shot list csv data with each "Video_Prompt" field filled out. include the Shot_ID and Type fields for these rows.  Do NOT include any other text in your reply.  Enclose the video prompt column in "" to prevent any commas inside the video prompt from corrupting the data.
Follow the ltx prompt guide below to create each "action" prompt, but keep in mind that any recuring characters, objects, or locations in the story must be fully described in each prompt as the video model will have no knowledge of what came before.  Give each character a name and refer to them by name in the prompt along with their descriptions.  It is CRITICAL that we have a description of the character's build, face, hair, and clothing in EACH prompt to keep them consistent between shots.
1. Establish the Shot
Use cinematography terms that match your intended genre. Include shot scale or category-specific characteristics to refine the visual style.
2. Set the Scene
Describe lighting conditions, color palette, surface textures, and atmosphere to establish mood and tone.
3. Describe the Action
Write the core action as a natural sequence, flowing clearly from beginning to end.
4. Define the Character(s)
Include age, hairstyle, clothing, and distinguishing features. Express emotion through physical cues, not abstract labels.
5. Identify Camera Movement(s)
Specify how and when the camera moves. Describing how subjects appear after the movement helps the model complete the motion accurately.
6. Describe the Audio
Clearly describe ambient sound, music, speech, or singing.
Place spoken dialogue in quotation marks
Specify language and accent if needed
For Best Results
Write your prompt as a single flowing paragraph
Use present tense verbs for action and movement
Match the level of detail to the shot scale
(close-ups need more detail than wide shots)
Describe camera movement relative to the subject
Aim for 4-8 descriptive sentences

Main Character's Gender: {gender}
Main Character and Setting Description: {character_desc}
Rough Concept: {concept}

Shot list:
{shot_list}"""

ALL_VOCALS_PROMPT_TEMPLATE = """Create a music video via AI video prompts for the following song (see song lyrics below).  See the attached CSV formatted shot list with durations and frame counts. Every shot in this video is a vocal/performance shot. Create detailed, visually compelling prompts for each shot that combine performance elements with creative visual storytelling aligned to the song's themes. Do not include any guns in the story as the LTX video model censors them.  Do not use any words in your descriptions like, painted, sketched, or drawn to prevent the video model from creating animated shots.  Return the shot list in CSV format with just the "Shot_ID", "Type" and "Video_Prompt" columns.  Do NOT include any other text in your reply.  Enclose the video prompt column in "" to prevent any commas inside the video prompt from corrupting the data.

Follow the ltx prompt guide below to create each prompt, but keep in mind that any recuring characters, objects, or locations in the story must be fully described in each prompt as the video model will have no knowledge of what came before.  Give each character a name and refer to them by name in the prompt along with their descriptions.  It is CRITICAL that we have a description of the character's build, face, hair, and clothing in EACH prompt to keep them consistent between shots.

Establish the shot. Use cinematography terms that match your preferred film genre. Include aspects like scale or specific category characteristics to further refine the style you're looking for.

Set the scene. Describe lighting conditions, color palette, surface textures, and atmosphere to shape the mood.

Describe the action. Write the core action as a natural sequence, flowing from beginning to end.

Define your character(s). Include age, hairstyle, clothing, and distinguishing details. Express emotions through physical cues.

Identify camera movement(s). Specify when the view should shift and how. Including how subjects or objects appear after the camera motion gives the model a better idea of how to finish the motion.

Keep your prompt in a single flowing paragraph to give the model a cohesive scene to work with.
Use present tense verbs to describe movement and action.
Match your detail to the shot scale. Closeups need more precise detail than wide shots.
When describing camera movement, focus on the camera's relationship to the subject.
You should expect to write 4 to 8 descriptive sentences to cover all the key aspects of the prompt.

Song Lyrics:
{lyrics}

User suggested plot concept:
{plot}

Singer/Band/Venue Description:
{performance_desc}

Shot list:
{shot_list}"""

BULK_PROMPT_TEMPLATE = """Create a music video via AI video prompts for the following song (see song lyrics below).  See the attached CSV formatted shot list with durations and frame counts. We need to tell a coherent story using the shots labeled "Action" in the type column.  Align your story loosely to the themes and metaphors present in the song's lyrics, or the user suggested plot concept (if present), but do not be afraid to get creative! Do not include any guns in the story as the LTX video model censors them.  Do not use any words in your descriptions like, painted, sketched, or drawn to prevent the video model from creating animated shots.  Return the shot list in CSV format with just the "Shot_ID", "Type" and "Video_Prompt" columns.  Leave the "Vocal" type rows video prompts blank, but include the Shot_ID and Type fields for these rows.  Do NOT include any other text in your reply.  Enclose the video prompt column in "" to prevent any commas inside the video prompt from corrupting the data.

Follow the ltx prompt guide below to create each "action" prompt, but keep in mind that any recuring characters, objects, or locations in the story must be fully described in each prompt as the video model will have no knowledge of what came before.  Give each character a name and refer to them by name in the prompt along with their descriptions.  It is CRITICAL that we have a description of the character's build, face, hair, and clothing in EACH prompt to keep them consistent between shots.

Establish the shot. Use cinematography terms that match your preferred film genre. Include aspects like scale or specific category characteristics to further refine the style you're looking for.

Set the scene. Describe lighting conditions, color palette, surface textures, and atmosphere to shape the mood.

Describe the action. Write the core action as a natural sequence, flowing from beginning to end.

Define your character(s). Include age, hairstyle, clothing, and distinguishing details. Express emotions through physical cues.

Identify camera movement(s). Specify when the view should shift and how. Including how subjects or objects appear after the camera motion gives the model a better idea of how to finish the motion.

Keep your prompt in a single flowing paragraph to give the model a cohesive scene to work with.
Use present tense verbs to describe movement and action.
Match your detail to the shot scale. Closeups need more precise detail than wide shots.
When describing camera movement, focus on the camera's relationship to the subject.
You should expect to write 4 to 8 descriptive sentences to cover all the key aspects of the prompt.

Song Lyrics:
{lyrics}

User suggested plot concept:
{plot}

Shot list:
{shot_list}"""

# ==========================================
# DEFAULT LLM PROMPT TEMPLATES
# ==========================================

# --- Plot Generation ---
DEFAULT_PLOT_SYSTEM_PROMPT_MUSIC = "You are a creative writer for music videos."
DEFAULT_PLOT_USER_TEMPLATE_MUSIC = (
    "Rough Concept: {concept}\n\nLyrics:\n{lyrics}\n\nTimeline:\n{timeline}\n\n"
    "Task: Write a cohesive linear plot summary for this video (max 300 words)."
)
DEFAULT_PLOT_SYSTEM_PROMPT_SCRIPTED = "You are a creative writer for short narrative films."
DEFAULT_PLOT_USER_TEMPLATE_SCRIPTED = (
    "Rough Concept: {concept}\n\n"
    "Task: Write a cohesive linear plot summary for this short narrative film (max 300 words). "
    "Focus on character arcs, settings, and dramatic moments."
)

# --- Performance Description ---
DEFAULT_PERF_SYSTEM_PROMPT_MUSIC = "You are a casting director and set designer."
DEFAULT_PERF_USER_TEMPLATE_MUSIC = (
    "Concept: {concept}\nPlot: {plot}\n{gender_instruction}\n"
    "Task: Invent and sescribe the physical appearance, proper name, age, hair, clothing, and style of a lead singer for the above song, specifically for an AI video generation model. "
    "Start with the phrase 'Handheld dynamic closeup shot of'. Do not include any details about the character that would be out of view in a close-up shot. "
    "End the description with; [name of singer] is careful to enunciate each word to the camera to account for their deaf sister's lip reading. "
    "Shot with a dynamic camera movement and slight handheld shake, shallow depth of field, dramatic chiaroscuro lighting, 85mm lens, 24fps, high contrast, crowd silhouettes, energetic atmosphere, cinematic color grading, [describe color pallet here] "
    "Keep it concise (5-6 sentences)."
)
DEFAULT_PERF_SYSTEM_PROMPT_SCRIPTED = "You are a casting director and set designer for short films."
DEFAULT_PERF_USER_TEMPLATE_SCRIPTED = (
    "Concept: {concept}\nPlot: {plot}\n{gender_instruction}\n"
    "Task: Describe the main character's physical appearance, style, and the primary setting/location, "
    "specifically for an AI video generation model. Include build, face, hair, clothing, and setting details. "
    "Keep it concise (3-4 sentences)."
)

# ==========================================
# GLOBAL MEMORY
# ==========================================
GLOBAL_SETTINGS_FILE = "global_settings.json"

def get_global_llm():
    try:
        if os.path.exists(GLOBAL_SETTINGS_FILE):
            with open(GLOBAL_SETTINGS_FILE, "r") as f:
                return json.load(f).get("last_llm", None)
    except:
        pass
    return None

def save_global_llm(model_id):
    try:
        data = {}
        if os.path.exists(GLOBAL_SETTINGS_FILE):
            with open(GLOBAL_SETTINGS_FILE, "r") as f:
                data = json.load(f)
        data["last_llm"] = model_id
        with open(GLOBAL_SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except:
        pass

def load_global_url_settings():
    global LTX_BASE_URL, LM_STUDIO_URL, VIDEO_BACKEND
    try:
        if os.path.exists(GLOBAL_SETTINGS_FILE):
            with open(GLOBAL_SETTINGS_FILE, "r") as f:
                data = json.load(f)
                LTX_BASE_URL = data.get("ltx_base_url", LTX_BASE_URL)
                LM_STUDIO_URL = data.get("lm_studio_url", LM_STUDIO_URL)
                VIDEO_BACKEND = data.get("video_backend", VIDEO_BACKEND)
    except:
        pass

def save_global_url_settings(ltx_url, lm_url, video_backend="LTX Desktop"):
    global LTX_BASE_URL, LM_STUDIO_URL, VIDEO_BACKEND
    LTX_BASE_URL = ltx_url.strip()
    LM_STUDIO_URL = lm_url.strip()
    VIDEO_BACKEND = video_backend
    try:
        data = {}
        if os.path.exists(GLOBAL_SETTINGS_FILE):
            with open(GLOBAL_SETTINGS_FILE, "r") as f:
                data = json.load(f)
        data["ltx_base_url"] = LTX_BASE_URL
        data["lm_studio_url"] = LM_STUDIO_URL
        data["video_backend"] = VIDEO_BACKEND
        with open(GLOBAL_SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)
        return "✅ Settings saved and applied."
    except Exception as e:
        return f"❌ Error saving settings: {e}"

load_global_url_settings()

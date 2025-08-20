# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" Main Mesop App """
import json
import random
from dataclasses import dataclass, field
import datetime #The following import is for time limit of viewing signed urls of GCS objects. currently it is 60 minutes.
import os

import mesop as me
import vertexai
# The following import is for generating signed URLs for GCS objects
from google.cloud import storage
from google.cloud.aiplatform import telemetry
from google.auth import default
from google.oauth2 import service_account
from vertexai.generative_models import (
    GenerationConfig,
    GenerativeModel,
    HarmCategory,
    Part,
)
from vertexai.preview.vision_models import ImageGenerationModel
from models.image_models import ImageModel
from config.default import Config
from prompts.critics import (
    MAGAZINE_EDITOR_PROMPT,
    REWRITER_PROMPT,
)
from svg_icon.svg_icon_component import svg_icon_component

def get_storage_client():
    """Get authenticated storage client for both local and Cloud Run environments"""
    try:
        # Check if we're running locally with service account key
        if os.path.exists("credentials.json"):
            credentials = service_account.Credentials.from_service_account_file(
                "credentials.json"
            )
            return storage.Client(credentials=credentials)
        else:
            # Running in Cloud Run or with default credentials
            return storage.Client()
    except Exception as e:
        print(f"Error creating storage client: {e}")
        # Fallback to default credentials
        return storage.Client()

# Initialize Configuration
cfg = Config()
vertexai.init(project=cfg.PROJECT_ID, location=cfg.LOCATION)

@me.stateclass
@dataclass
class State:
    """Mesop App State"""

    # Image generation model selection and output
    image_models: list[ImageModel] = field(default_factory=lambda: cfg.display_image_models.copy())
    image_output: list[str] = field(default_factory=list)
    image_commentary: str = ""
    image_model_name: str = cfg.MODEL_IMAGEN3_FAST

    # General UI state
    is_loading: bool = False
    show_advanced: bool = False

    # Image prompt and related settings
    image_prompt_input: str = ""
    image_prompt_placeholder: str = ""
    image_textarea_key: int = 0

    image_negative_prompt_input: str = ""
    image_negative_prompt_placeholder: str = ""
    image_negative_prompt_key: int = 0  # Or handle None later

    # Image generation parameters
    imagen_watermark: bool = True
    imagen_seed: int = 0
    imagen_image_count: int = 3

    # Image style modifiers
    image_content_type: str = "Photo"
    image_color_tone: str = "Cinematic"
    image_lighting: str = "None"
    image_composition: str = "Wide angle"
    image_aspect_ratio: str = "16:9"
    image_art_style: str = "None"
    image_mood_atmosphere: str = "None"
    image_texture: str = "None"
    
    # Phase 2: Subject-Specific Options
    image_subject_age: str = "None"
    image_subject_gender: str = "None"
    image_subject_clothing: str = "None"
    image_subject_hair: str = "None"
    image_environment_setting: str = "None"
    image_time_of_day: str = "None"
    image_weather_condition: str = "None"
    image_season: str = "None"
    
    # Phase 2: Advanced Composition Tools
    image_focal_length: str = "None"
    image_aperture: str = "None"
    image_camera_angle: str = "None"
    image_focus_technique: str = "None"
    image_motion_effect: str = "None"
    image_lens_type: str = "None"
    image_film_type: str = "None"


def on_image_input(e: me.InputEvent):
    """Image Input Event"""
    state = me.state(State)
    state.image_prompt_input = e.value


def on_blur_image_prompt(e: me.InputBlurEvent):
    """Image Blur Event"""
    me.state(State).image_prompt_input = e.value


def on_blur_image_negative_prompt(e: me.InputBlurEvent):
    """Image Blur Event"""
    me.state(State).image_negative_prompt_input = e.value


def on_click_generate_images(e: me.ClickEvent):
    """Click Event to generate images."""
    state = me.state(State)
    state.is_loading = True
    state.image_output.clear()
    yield
    generate_images(state.image_prompt_input)
    generate_compliment(state.image_prompt_input)
    state.is_loading = False
    yield


def on_select_image_count(e: me.SelectSelectionChangeEvent):
    """Change Event For Selecting an Image Model."""
    state = me.state(State)
    setattr(state, e.key, e.value)


def generate_images(input_txt: str):
    """Generate Images"""
    state = me.state(State)

    # handle condition where someone hits "random" but doens't modify
    if not input_txt and state.image_prompt_placeholder:
        input_txt = state.image_prompt_placeholder
    state.image_output.clear()
    modifiers = []
    for mod in cfg.image_modifiers:
        if mod != "aspect_ratio":
            if getattr(state, f"image_{mod}") != "None":
                modifiers.append(getattr(state, f"image_{mod}"))
    prompt_modifiers = ", ".join(modifiers)
    prompt = f"{input_txt} {prompt_modifiers}"
    print(f"prompt: {prompt}")
    if state.image_negative_prompt_input:
        print(f"negative prompt: {state.image_negative_prompt_input}")
    print(f"model: {state.image_model_name}")
    image_generation_model = ImageGenerationModel.from_pretrained(
        state.image_model_name
    )
    number_of_images = int(state.imagen_image_count)

    generation_params = {
        "prompt": prompt,
        "add_watermark": True,
        "aspect_ratio": getattr(state, "image_aspect_ratio"),
        "number_of_images": number_of_images,
        "language": "auto",
        "negative_prompt": state.image_negative_prompt_input,
    }

    folder_name = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    if state.image_model_name == cfg.MODEL_IMAGEN4_ULTRA:
        generation_params["number_of_images"] = 1
    else:
        generation_params["output_gcs_uri"] = f"gs://{cfg.IMAGE_CREATION_BUCKET}/{folder_name}"

    # Save prompt to a file
    storage_client = get_storage_client()
    bucket = storage_client.bucket(cfg.IMAGE_CREATION_BUCKET)
    prompt_filename = f"{folder_name}/prompt.txt"
    prompt_blob = bucket.blob(prompt_filename)
    prompt_blob.upload_from_string(prompt, content_type="text/plain")

    response = image_generation_model.generate_images(**generation_params)

    print(f"Response object: {response}")

    if state.image_model_name == cfg.MODEL_IMAGEN4_ULTRA:
        storage_client = get_storage_client()
        bucket = storage_client.bucket(cfg.IMAGE_CREATION_BUCKET)
        filename = f"{folder_name}/image-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.png"
        blob = bucket.blob(filename)
        blob.upload_from_string(response[0]._image_bytes, content_type="image/png")
        gcs_uri = f"gs://{cfg.IMAGE_CREATION_BUCKET}/{filename}"
        state.image_output.append(gcs_uri)
    else:
        try:
            for idx, img in enumerate(response):
                print(
                    f"generated image: {idx} size: {len(img._as_base64_string())} at {img._gcs_uri}"
                )
                state.image_output.append(img._gcs_uri) # type: ignore
        except Exception as e:
            print(f"Error processing image response: {e}")
            # Handle the case where the response is a single image object
            if not isinstance(response, list):
                try:
                    print(
                        f"generated image: 0 size: {len(response._as_base64_string())} at {response._gcs_uri}"
                    )
                    state.image_output.append(response._gcs_uri) # type: ignore
                except Exception as e2:
                    print(f"Error processing single image response: {e2}")


def random_prompt_generator(e: me.ClickEvent):
    """Click Event to generate a random prompt from a list of predefined prompts."""
    state = me.state(State)
    with open(cfg.IMAGEN_PROMPTS_JSON, "r", encoding="utf-8") as file:
        data = file.read()
    prompts = json.loads(data)
    random_prompt = random.choice(prompts["imagen"])
    state.image_prompt_placeholder = random_prompt
    on_image_input(
        me.InputEvent(key=str(state.image_textarea_key), value=random_prompt)
    )
    print(f"preset chosen: {random_prompt}")
    yield


# advanced controls
def on_click_advanced_controls(e: me.ClickEvent):
    """Click Event to toggle advanced controls."""
    me.state(State).show_advanced = not me.state(State).show_advanced


def on_click_clear_images(e: me.ClickEvent):
    """Click Event to clear images."""
    state = me.state(State)
    state.image_prompt_input = ""
    state.image_prompt_placeholder = ""
    state.image_output.clear()
    state.image_negative_prompt_input = ""
    state.image_textarea_key += 1
    state.image_negative_prompt_key += 1


def on_selection_change_image(e: me.SelectSelectionChangeEvent):
    """Change Event For Selecting an Image Model."""
    state = me.state(State)
    print(f"changed: {e.key}={e.value}")
    setattr(state, f"image_{e.key}", e.value)


def on_click_rewrite_prompt(e: me.ClickEvent):
    """Click Event to rewrite prompt."""
    state = me.state(State)
    if state.image_prompt_input:
        rewritten = rewrite_prompt(state.image_prompt_input)
        state.image_prompt_input = rewritten
        state.image_prompt_placeholder = rewritten


def rewrite_prompt(original_prompt: str):
    """
    Outputs a rewritten prompt

    Args:
        original_prompt (str): artists's original prompt
    """
    # state = me.state(State)
    with telemetry.tool_context_manager("creative-studio"):
        rewriting_model = GenerativeModel(cfg.MODEL_GEMINI_MULTIMODAL)
    model_config = cfg.gemini_settings
    generation_cfg = GenerationConfig(
        temperature=model_config.generation["temperature"],
        max_output_tokens=model_config.generation["max_output_tokens"],
    )
    safety_filters = {
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: model_config.safety_settings[
            "DANGEROUS_CONTENT"
        ],
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: model_config.safety_settings[
            "HATE_SPEECH"
        ],
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: model_config.safety_settings[
            "SEXUALLY_EXPLICIT"
        ],
        HarmCategory.HARM_CATEGORY_HARASSMENT: model_config.safety_settings[
            "HARASSMENT"
        ],
    }
    response = rewriting_model.generate_content(
        REWRITER_PROMPT.format(original_prompt),
        generation_config=generation_cfg,
        safety_settings=safety_filters,
    )
    print(f"asked to rewrite: '{original_prompt}")
    print(f"rewritten as: {response.text}")
    return response.text


def generate_compliment(generation_instruction: str):
    """
    Outputs a Gemini generated comment about images
    """
    state = me.state(State)
    with telemetry.tool_context_manager("creative-studio"):
        generation_model = GenerativeModel(cfg.MODEL_GEMINI_MULTIMODAL)
    model_config = cfg.gemini_settings
    generation_cfg = GenerationConfig(
        temperature=model_config.generation["temperature"],
        max_output_tokens=model_config.generation["max_output_tokens"],
    )
    safety_filters = {
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: model_config.safety_settings[
            "DANGEROUS_CONTENT"
        ],
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: model_config.safety_settings[
            "HATE_SPEECH"
        ],
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: model_config.safety_settings[
            "SEXUALLY_EXPLICIT"
        ],
        HarmCategory.HARM_CATEGORY_HARASSMENT: model_config.safety_settings[
            "HARASSMENT"
        ],
    }
    prompt_parts = []
    for idx, img in enumerate(state.image_output):
        # not bytes
        # prompt_parts.append(Part.from_data(data=img, mime_type="image/png"))
        # now gcs uri
        prompt_parts.append(f"""image {idx+1}""")
        prompt_parts.append(Part.from_uri(uri=img, mime_type="image/png"))
    prompt_parts.append(MAGAZINE_EDITOR_PROMPT.format(generation_instruction))
    response = generation_model.generate_content(
        prompt_parts,
        generation_config=generation_cfg,
        safety_settings=safety_filters,
    )
    state.image_commentary = response.text


@me.page(
    path="/",
    security_policy=me.SecurityPolicy(
        allowed_script_srcs=["https://cdn.jsdelivr.net"],
        allowed_connect_srcs=["https://cdn.jsdelivr.net"],
        dangerously_disable_trusted_types=True,
    ),
    title="Imagen Studio | Vertex AI",
)
def app():
    """Mesop App"""
    state = me.state(State)
    with me.box(
        style=me.Style(
            display="flex",
            flex_direction="column",
            height="100%",
        ),
    ):
        with me.box(
            style=me.Style(
                background="#f0f4f8",
                height="100%",
                overflow_y="scroll",
                margin=me.Margin(bottom=20),
            )
        ):
            with me.box(
                style=me.Style(
                    background="#f0f4f8",
                    padding=me.Padding(top=24, left=24, right=24, bottom=24),
                    display="flex",
                    flex_direction="column",
                )
            ):
                with me.box(
                    style=me.Style(
                        display="flex",
                        justify_content="space-between",
                    )
                ):
                    with me.box(
                        style=me.Style(display="flex", flex_direction="row", gap=5)
                    ):
                        me.icon(icon="auto_fix_high")
                        me.text(
                            cfg.TITLE,
                            type="headline-5",
                            style=me.Style(font_family="Google Sans"),
                        )
                    image_model_options = []
                    for c in state.image_models:
                        image_model_options.append(
                            me.SelectOption(
                                label=c.get("display"), value=c.get("model_name")
                            )
                        )
                    me.select(
                        label="Imagen version",
                        options=image_model_options,
                        key="model_name",
                        on_selection_change=on_selection_change_image,
                        value=state.image_model_name,
                    )

                # Prompt
                with me.box(
                    style=me.Style(
                        margin=me.Margin(left="auto", right="auto"),
                        width="min(1024px, 100%)",
                        gap="24px",
                        flex_grow=1,
                        display="flex",
                        flex_wrap="wrap",
                        flex_direction="column",
                    )
                ):
                    with me.box(style=_BOX_STYLE):
                        me.text(
                            "Prompt for image generation",
                            style=me.Style(font_weight=500),
                        )
                        me.box(style=me.Style(height=16))
                        me.textarea(
                            key=str(state.image_textarea_key),
                            # on_input=on_image_input,
                            on_blur=on_blur_image_prompt,
                            rows=3,
                            autosize=True,
                            max_rows=10,
                            style=me.Style(width="100%"),
                            value=state.image_prompt_placeholder,
                        )
                        # Prompt buttons
                        me.box(style=me.Style(height=12))
                        with me.box(
                            style=me.Style(
                                display="flex", justify_content="space-between"
                            )
                        ):
                            me.button(
                                "Clear",
                                color="primary",
                                type="stroked",
                                on_click=on_click_clear_images,
                            )

                            me.button(
                                "Random",
                                color="primary",
                                type="stroked",
                                on_click=random_prompt_generator,
                                style=me.Style(color="#1A73E8"),
                            )
                            # prompt rewriter
                            # disabled = not state.image_prompt_input if not state.image_prompt_input else False
                            with me.content_button(
                                on_click=on_click_rewrite_prompt,
                                type="stroked",
                                # disabled=disabled,
                            ):
                                with me.tooltip(message="rewrite prompt with Gemini"):
                                    with me.box(
                                        style=me.Style(
                                            display="flex",
                                            gap=3,
                                            align_items="center",
                                        )
                                    ):
                                        me.icon("auto_awesome")
                                        me.text("Rewriter")
                            # generate
                            me.button(
                                "Generate",
                                color="primary",
                                type="flat",
                                on_click=on_click_generate_images,
                            )

                    # Modifiers
                    with me.box(style=_BOX_STYLE):
                        with me.box(
                            style=me.Style(
                                display="flex",
                                justify_content="space-between",
                                gap=2,
                                width="100%",
                            )
                        ):
                            if state.show_advanced:
                                with me.content_button(
                                    on_click=on_click_advanced_controls
                                ):
                                    with me.tooltip(message="hide advanced controls"):
                                        with me.box(style=me.Style(display="flex")):
                                            me.icon("expand_less")
                            else:
                                with me.content_button(
                                    on_click=on_click_advanced_controls
                                ):
                                    with me.tooltip(message="show advanced controls"):
                                        with me.box(style=me.Style(display="flex")):
                                            me.icon("expand_more")

                            # Default Modifiers
                            me.select(
                                label="Aspect Ratio",
                                options=[
                                    me.SelectOption(label="1:1", value="1:1"),
                                    me.SelectOption(label="3:4", value="3:4"),
                                    me.SelectOption(label="4:3", value="4:3"),
                                    me.SelectOption(label="16:9", value="16:9"),
                                    me.SelectOption(label="9:16", value="9:16"),
                                ],
                                key="aspect_ratio",
                                on_selection_change=on_selection_change_image,
                                style=me.Style(width="160px"),
                                value=state.image_aspect_ratio,
                            )
                            content_type_options = []
                            for content in [
                                "None",
                                "Abstract",
                                "Aerial",
                                "Architecture",
                                "Art",
                                "Commercial",
                                "Conceptual",
                                "Concert",
                                "Documentary",
                                "Editorial",
                                "Fashion",
                                "Fine Art",
                                "Food Photography",
                                "Illustration",
                                "Landscape",
                                "Macro",
                                "Minimalist",
                                "Modern",
                                "Night Photography",
                                "Painting",
                                "Photo",
                                "Portrait",
                                "Product Photography",
                                "Sketch",
                                "Sports",
                                "Still Life",
                                "Street Photography",
                                "Surreal",
                                "Travel",
                                "Underwater",
                                "Vintage",
                                "Wedding",
                                "Wildlife",
                            ]:
                                content_type_options.append(
                                    me.SelectOption(label=content, value=content)
                                )
                            me.select(
                                label="Content Type",
                                options=content_type_options,
                                key="content_type",
                                on_selection_change=on_selection_change_image,
                                style=me.Style(width="160px"),
                                value=state.image_content_type,
                            )

                            color_and_tone_options = []
                            for c in [
                                "None",
                                "Cinematic",
                                "4K HDR",
                                "Analogous colors",
                                "Black and white",
                                "Bleach bypass",
                                "Blue tone",
                                "Color grading",
                                "Color splash",
                                "Complementary colors",
                                "Cool tone",
                                "Cross processed",
                                "Cyan tone",
                                "Desaturated",
                                "Duotone",
                                "Earth tones",
                                "Film noir",
                                "Golden",
                                "Gradient",
                                "Green tone",
                                "High contrast",
                                "Infrared",
                                "Jewel tones",
                                "Kodachrome",
                                "Low contrast",
                                "Magenta tone",
                                "Monochromatic",
                                "Muted color",
                                "Muted orange warm tones",
                                "Neon",
                                "Ombre",
                                "Orange tone",
                                "Pastel color",
                                "Pink tone",
                                "Polaroid",
                                "Purple tone",
                                "Red tone",
                                "Saturated",
                                "Sepia",
                                "Split complementary",
                                "Technicolor",
                                "Tetradic colors",
                                "Toned image",
                                "Triadic colors",
                                "Vibrant",
                                "Vintage",
                                "Warm tone",
                                "Yellow tone",
                            ]:
                                color_and_tone_options.append(
                                    me.SelectOption(label=c, value=c)
                                )
                            me.select(
                                label="Color & Tone",
                                options=color_and_tone_options,
                                key="color_tone",
                                on_selection_change=on_selection_change_image,
                                style=me.Style(width="160px"),
                                value=state.image_color_tone,
                            )

                            lighting_options = []
                            for l in [
                                "None",
                                "Accent lighting",
                                "Ambient light",
                                "Backlighting",
                                "Background light",
                                "Beauty lighting",
                                "Blue hour",
                                "Bottom lighting",
                                "Broad lighting",
                                "Butterfly lighting",
                                "Candlelight",
                                "Chiaroscuro",
                                "Cinematic lighting",
                                "Cloudy",
                                "Cold lighting",
                                "Concert lighting",
                                "Contre-jour",
                                "Dawn",
                                "Diffused light",
                                "Directional light",
                                "Dramatic light",
                                "Dusk",
                                "Fill light",
                                "Firelight",
                                "Flash photography",
                                "Floodlight",
                                "Fluorescent",
                                "Front lighting",
                                "God rays",
                                "Golden hour",
                                "Hair light",
                                "Hard light",
                                "Harsh light",
                                "High key lighting",
                                "High Contrast",
                                "Incandescent",
                                "Key light",
                                "LED lighting",
                                "Long-time exposure",
                                "Loop lighting",
                                "Low key lighting",
                                "Low lighting",
                                "Magic hour",
                                "Moonlight",
                                "Moody lighting",
                                "Multiexposure",
                                "Natural light",
                                "Neon lighting",
                                "Overcast",
                                "Rembrandt lighting",
                                "Rim lighting",
                                "Ring light",
                                "Short lighting",
                                "Side lighting",
                                "Silhouette",
                                "Soft light",
                                "Softbox",
                                "Split lighting",
                                "Spotlight",
                                "Stage lighting",
                                "Stormy lighting",
                                "Strobe light",
                                "Studio light",
                                "Sunbeam",
                                "Sunny",
                                "Surreal lighting",
                                "Top lighting",
                                "Twilight",
                                "Umbrella lighting",
                                "Underwater lighting",
                                "Volumetric lighting",
                                "Warm lighting",
                            ]:
                                lighting_options.append(
                                    me.SelectOption(label=l, value=l)
                                )
                            me.select(
                                label="Lighting",
                                options=lighting_options,
                                key="lighting",
                                on_selection_change=on_selection_change_image,
                                value=state.image_lighting,
                            )

                            composition_options = []
                            for c in [
                                "None",
                                "Shallow depth of field",
                                "Abstract composition",
                                "Action shot",
                                "Aerial",
                                "Asymmetrical",
                                "Backlit",
                                "Background focus",
                                "Bird's eye view",
                                "Bokeh",
                                "Busy composition",
                                "Candid",
                                "Centered composition",
                                "Circular composition",
                                "Closeup",
                                "Collage",
                                "Depth of field",
                                "Diagonal composition",
                                "Diptych",
                                "Double exposure",
                                "Dutch angle",
                                "Dynamic composition",
                                "Environmental portrait",
                                "Extreme closeup",
                                "Extreme wide shot",
                                "Eye level",
                                "Fish eye",
                                "Foreground focus",
                                "Frame within frame",
                                "From below",
                                "Full body shot",
                                "Geometric",
                                "Golden ratio",
                                "Group composition",
                                "Half body shot",
                                "Head and shoulders",
                                "High angle",
                                "Isolated subject",
                                "Knolling",
                                "Landscape photography",
                                "Layered composition",
                                "Leading lines",
                                "Long shot",
                                "Low angle",
                                "Macro photography",
                                "Medium shot",
                                "Minimalist composition",
                                "Montage",
                                "Negative space",
                                "Off-center",
                                "Organic shapes",
                                "Over the shoulder",
                                "Panoramic",
                                "Photographed through window",
                                "Point of view",
                                "Posed",
                                "Profile shot",
                                "Reflection",
                                "Rule of thirds",
                                "Shot from above",
                                "Shot from below",
                                "Silhouette",
                                "Still life",
                                "Straight angle",
                                "Surface detail",
                                "Symmetrical",
                                "Taken from far away",
                                "Three-quarter view",
                                "Tilt-shift",
                                "Triptych",
                                "Wide angle",
                                "Worm's eye view",
                            ]:
                                composition_options.append(
                                    me.SelectOption(label=c, value=c)
                                )
                            me.select(
                                label="Composition",
                                options=composition_options,
                                key="composition",
                                on_selection_change=on_selection_change_image,
                                value=state.image_composition,
                            )

                        # Second row of modifiers - New Phase 1 Features
                        with me.box(
                            style=me.Style(
                                display="flex",
                                justify_content="center",
                                gap=2,
                                width="100%",
                                margin=me.Margin(top=10),
                                flex_wrap="wrap",
                            )
                        ):
                            # Art Style
                            art_style_options = []
                            for style in [
                                "None",
                                "Realistic",
                                "Photorealistic",
                                "Hyperrealistic",
                                "Studio Ghibli",
                                "Anime",
                                "Manga",
                                "Disney",
                                "Pixar",
                                "Impressionist painting",
                                "Van Gogh",
                                "Monet",
                                "Picasso",
                                "Surreal",
                                "Salvador Dali",
                                "Abstract",
                                "Minimalist",
                                "Fantasy",
                                "Pop Art",
                                "Andy Warhol",
                                "Watercolor",
                                "Oil Painting",
                                "Acrylic",
                                "Digital art",
                                "Concept Art",
                                "3D Render",
                                "Pixel Art",
                                "Vector Art",
                                "Technical pencil drawing",
                                "Charcoal drawing",
                                "Color pencil drawing",
                                "Pastel painting",
                                "Sketch",
                                "Pencil Drawing",
                                "Charcoal",
                                "Ink Drawing",
                                "Pastel",
                                "Art Nouveau",
                                "Art Deco (poster)",
                                "Renaissance painting",
                                "Baroque",
                                "Gothic",
                                "Cyberpunk",
                                "Steampunk",
                                "Retro",
                                "Vintage",
                                "Grunge",
                            ]:
                                art_style_options.append(
                                    me.SelectOption(label=style, value=style)
                                )
                            me.select(
                                label="Art Style",
                                options=art_style_options,
                                key="art_style",
                                on_selection_change=on_selection_change_image,
                                style=me.Style(width="160px"),
                                value=state.image_art_style,
                            )

                            # Mood/Atmosphere
                            mood_options = []
                            for mood in [
                                "None",
                                "Futuristic",
                                "Calm",
                                "Peaceful",
                                "Serene",
                                "Tranquil",
                                "Energetic",
                                "Dynamic",
                                "Vibrant",
                                "Lively",
                                "Mysterious",
                                "Enigmatic",
                                "Dark",
                                "Moody",
                                "Romantic",
                                "Dreamy",
                                "Whimsical",
                                "Dramatic",
                                "Intense",
                                "Epic",
                                "Heroic",
                                "Melancholic",
                                "Nostalgic",
                                "Joyful",
                                "Cheerful",
                                "Uplifting",
                                "Ominous",
                                "Foreboding",
                                "Ethereal",
                                "Magical",
                                "Mystical",
                                "Cozy",
                                "Warm",
                                "Cold",
                                "Lonely",
                                "Crowded",
                                "Bustling",
                                "Quiet",
                                "Loud",
                                "Chaotic",
                                "Orderly",
                                "Ancient",
                                "Timeless",
                            ]:
                                mood_options.append(
                                    me.SelectOption(label=mood, value=mood)
                                )
                            me.select(
                                label="Mood/Atmosphere",
                                options=mood_options,
                                key="mood_atmosphere",
                                on_selection_change=on_selection_change_image,
                                style=me.Style(width="160px"),
                                value=state.image_mood_atmosphere,
                            )

                            # Texture
                            texture_options = []
                            for texture in [
                                "None",
                                "Smooth",
                                "Rough",
                                "Glossy",
                                "Matte",
                                "Metallic",
                                "Shiny",
                                "Reflective",
                                "Realistic Human skin texture",
                                "Soft skin",
                                "Detailed skin",
                                "Pore detail",
                                "Skin imperfections",
                                "Natural complexion",
                                "Healthy skin",
                                "Youthful skin",
                                "Mature skin",
                                "Fabric",
                                "Cotton",
                                "Silk",
                                "Velvet",
                                "Leather",
                                "Wood",
                                "Oak",
                                "Pine",
                                "Bamboo",
                                "Stone",
                                "Marble",
                                "Granite",
                                "Concrete",
                                "Brick",
                                "Glass",
                                "Crystal",
                                "Plastic",
                                "Rubber",
                                "Paper",
                                "Cardboard",
                                "Sand",
                                "Gravel",
                                "Fur",
                                "Feathers",
                                "Scales",
                                "Bark",
                                "Moss",
                                "Rust",
                                "Weathered",
                                "Cracked",
                                "Worn",
                                "Polished",
                                "Brushed",
                                "Hammered",
                                "Embossed",
                                "Textured",
                            ]:
                                texture_options.append(
                                    me.SelectOption(label=texture, value=texture)
                                )
                            me.select(
                                label="Texture",
                                options=texture_options,
                                key="texture",
                                on_selection_change=on_selection_change_image,
                                style=me.Style(width="160px"),
                                value=state.image_texture,
                            )

                            # Lens Type
                            lens_type_options = [
                                me.SelectOption(label="None", value="None"),
                                me.SelectOption(label="Fisheye", value="Fisheye"),
                                me.SelectOption(label="Ultra-Wide", value="Ultra-Wide)"),
                                me.SelectOption(label="Wide Angle)", value="Wide Angle"),
                                me.SelectOption(label="Cinematic Prime", value="Cinematic Prime"),
                                me.SelectOption(label="Standard", value="Standard"),
                                me.SelectOption(label="Macro Standard", value="Macro"),
                                me.SelectOption(label="Telephoto (85mm)", value="Telephoto"),
                                me.SelectOption(label="Macro", value="Macro 105mm"),
                                me.SelectOption(label="Anamorphic", value="Anamorphic"),
                            ]
                            me.select(
                                label="Lens Type",
                                options=lens_type_options,
                                key="lens_type",
                                on_selection_change=on_selection_change_image,
                                style=me.Style(width="160px"),
                                value=state.image_lens_type,
                            )

                        # Third row of modifiers - Phase 2: Subject-Specific Options (Advanced)
                        if state.show_advanced:
                            # Subject Details
                            with me.box(
                                style=me.Style(
                                    display="flex",
                                    justify_content="center",
                                    gap=2,
                                    width="100%",
                                    margin=me.Margin(top=10),
                                    flex_wrap="wrap",
                                )
                            ):
                                # Subject Age
                                subject_age_options = []
                                for age in ["None", "Child", "Elderly", "Middle-aged", "Senior", "Teen", "Young Adult"]:
                                    subject_age_options.append(me.SelectOption(label=age, value=age))
                                me.select(
                                    label="Subject Age",
                                    options=subject_age_options,
                                    key="subject_age",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_subject_age,
                                )

                                # Facial Expression
                                facial_expression_options = []
                                for expression in ["None", "Angry", "Calm", "Cheerful", "Confident", "Contemplative", "Curious", "Determined", "Disappointed", "Excited", "Focused", "Happy", "Joyful", "Laughing", "Melancholic", "Peaceful", "Playful", "Relaxed", "Sad", "Serious", "Smiling", "Surprised", "Thoughtful", "Worried"]:
                                    facial_expression_options.append(me.SelectOption(label=expression, value=expression))
                                me.select(
                                    label="Facial Expression",
                                    options=facial_expression_options,
                                    key="subject_gender",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_subject_gender,
                                )

                                # Subject Clothing
                                subject_clothing_options = []
                                for clothing in ["None", "Bohemian", "Business", "Casual", "Elegant", "Evening wear", "Formal", "Minimalist", "Modern", "Professional", "Sporty", "Streetwear", "Summer clothes", "Traditional", "Vintage", "Winter clothes"]:
                                    subject_clothing_options.append(me.SelectOption(label=clothing, value=clothing))
                                me.select(
                                    label="Subject Clothing",
                                    options=subject_clothing_options,
                                    key="subject_clothing",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_subject_clothing,
                                )

                                # Subject Hair
                                subject_hair_options = []
                                for hair in ["None", "Bald", "Black", "Blonde", "Braided", "Brunette", "Colorful", "Curly", "Gray", "Long", "Medium", "Messy", "Natural", "Ponytail", "Red", "Short", "Straight", "Styled", "Wavy"]:
                                    subject_hair_options.append(me.SelectOption(label=hair, value=hair))
                                me.select(
                                    label="Subject Hair",
                                    options=subject_hair_options,
                                    key="subject_hair",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_subject_hair,
                                )

                            # Environment Details
                            with me.box(
                                style=me.Style(
                                    display="flex",
                                    justify_content="center",
                                    gap=2,
                                    width="100%",
                                    margin=me.Margin(top=10),
                                    flex_wrap="wrap",
                                )
                            ):
                                # Environment Setting
                                environment_options = []
                                for env in ["None", "Beach", "Cafe", "City", "Desert", "Forest", "Gallery", "Home", "Indoor", "Mountain", "Museum", "Natural setting", "Office", "Outdoor", "Park", "Restaurant", "Rural", "Street", "Studio", "Urban"]:
                                    environment_options.append(me.SelectOption(label=env, value=env))
                                me.select(
                                    label="Environment",
                                    options=environment_options,
                                    key="environment_setting",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_environment_setting,
                                )

                                # Time of Day
                                time_options = []
                                for time in ["None", "Afternoon", "Blue hour", "Dawn", "Evening", "Golden hour", "Midnight", "Morning", "Night", "Noon", "Sunrise", "Sunset", "Twilight"]:
                                    time_options.append(me.SelectOption(label=time, value=time))
                                me.select(
                                    label="Time of Day",
                                    options=time_options,
                                    key="time_of_day",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_time_of_day,
                                )

                                # Weather Condition
                                weather_options = []
                                for weather in ["None", "Clear sky", "Cloudy", "Cold", "Dry", "Foggy", "Humid", "Misty", "Overcast", "Partly cloudy", "Rainy", "Snowy", "Stormy", "Sunny", "Warm", "Windy"]:
                                    weather_options.append(me.SelectOption(label=weather, value=weather))
                                me.select(
                                    label="Weather",
                                    options=weather_options,
                                    key="weather_condition",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_weather_condition,
                                )

                                # Season
                                season_options = []
                                for season in ["None", "Autumn", "Early spring", "Fall", "Holiday season", "Late summer", "Mid-winter", "Spring", "Summer", "Winter"]:
                                    season_options.append(me.SelectOption(label=season, value=season))
                                me.select(
                                    label="Season",
                                    options=season_options,
                                    key="season",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_season,
                                )

                            # Composition Tools
                            with me.box(
                                style=me.Style(
                                    display="flex",
                                    justify_content="center",
                                    gap=2,
                                    width="100%",
                                    margin=me.Margin(top=10),
                                    flex_wrap="wrap",
                                )
                            ):
                                # Camera Angle
                                camera_angle_options = [me.SelectOption(label="None", value="None")]
                                for angle in ["Eye-Level", "Low-Angle", "High-Angle", "Bird's-Eye View", "Dutch Angle"]:
                                    camera_angle_options.append(me.SelectOption(label=angle, value=angle))
                                me.select(
                                    label="Camera Angle",
                                    options=camera_angle_options,
                                    key="camera_angle",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_camera_angle,
                                )

                                # Aperture
                                aperture_options = [me.SelectOption(label="None", value="None")]
                                for aperture in [
                                    "f/1.2",  # Ultra wide, specialty portrait lenses
                                    "f/1.4",  
                                    "f/1.8",  # Very common fast prime lenses
                                    "f/2",
                                    "f/2.8",
                                    "f/4",
                                    "f/5.6",
                                    "f/8",
                                    "f/11",
                                    "f/16",
                                    "f/22",   # Very narrow, landscape, max DoF
                                ]:
                                    aperture_options.append(me.SelectOption(label=aperture, value=aperture))
                                me.select(
                                    label="Aperture",
                                    options=aperture_options,
                                    key="aperture",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_aperture,
                                )

                                # Film Type
                                film_type_options = [me.SelectOption(label="None", value="None")]
                                for film in ["black and white", "polaroid", "Film noir", "duotone", "Grainy film", "Sepia tone"]:
                                    film_type_options.append(me.SelectOption(label=film, value=film))
                                me.select(
                                    label="Film Type",
                                    options=film_type_options,
                                    key="film_type",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_film_type,
                                )

                                # Depth of Field
                                # Focus Technique
                                focus_technique_options = [
                                    me.SelectOption(label="None", value="None"),
                                     # Common cinematic/photography focus styles
                                    me.SelectOption(label="-Soft focus (Dreamy)", value="Soft focus"),
                                    me.SelectOption(label="-Deep focus (Everything sharp)", value="Deep focus"),
                                    me.SelectOption(label="-Zone focusing (street photography)", value="Zone focusing"),
                                    me.SelectOption(label="-Shallow focus (bokeh)", value="Shallow focus"),
                                    me.SelectOption(label="-Selective focus (Isolate a specific detail)", value="Selective focus"),
                                    me.SelectOption(label="-Split diopter (Multi focus with bokeh)", value="Split diopter"),
                                    me.SelectOption(label="-Follow focus (moving subject)", value="Follow focus"),
                                    me.SelectOption(label="-Motion blur (Dynamic movement)", value="Motion blur"),

                                ]
                                me.select(
                                    label="Focus Technique",
                                    options=focus_technique_options,
                                    key="focus_technique",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_focus_technique,
                                )

                                # Focal Length
                                focal_length_options = [
                                    me.SelectOption(label="None", value="None"),
                                    # Wide / Ultra-wide
                                    me.SelectOption(label="-10mm (Ultra wide-angle, Landscapes, Architecture, Long exposure.)", value="10mm"),
                                    me.SelectOption(label="-24mm (Wide-angle, Environmental portraits, Street, Travel.)", value="24mm"),
                                    me.SelectOption(label="-35mm (Street, Documentary, Environmental portraits.)", value="35mm"),
                                    # Standard range
                                    me.SelectOption(label="-50mm (Standard, Classic portraits, Everyday photography, Natural perspective.)", value="50mm"),
                                    # Macro / Still life
                                    me.SelectOption(label="-60mm (Macro, Still life, Controlled lighting, Product photography.)", value="60mm"),
                                    # Portrait primes
                                    me.SelectOption(label="-85mm (Portraits, Bokeh, Shallow depth of field, Classic headshots.)", value="85mm"),
                                    me.SelectOption(label="-105mm (Macro, Portraits, Short telephoto, Precise focusing.)", value="105mm"),
                                    # Telephoto range
                                    me.SelectOption(label="-200mm (Portraits, Sports, Compression effect, Telephoto.)", value="200mm"),
                                    me.SelectOption(label="-400mm (Sports, Wildlife, Action, Super telephoto, Fast shutter.)", value="400mm"),
                                ]
                                me.select(
                                    label="Focal Length",
                                    options=focal_length_options,
                                    key="focal_length",
                                    on_selection_change=on_selection_change_image,
                                    style=me.Style(width="160px"),
                                    value=state.image_focal_length,
                                )

                        # Advanced controls
                        # negative prompt
                        with me.box(
                            style=me.Style(
                                display="flex",
                                flex_direction="row",
                                gap=5,
                            )
                        ):
                            if state.show_advanced:
                                me.box(style=me.Style(width=67))
                                me.input(
                                    label="negative phrases",
                                    on_blur=on_blur_image_negative_prompt,
                                    value=state.image_negative_prompt_placeholder,
                                    key=str(state.image_negative_prompt_key),
                                    style=me.Style(
                                        width="350px",
                                    ),
                                )
                                me.select(
                                    label="number of images",
                                    value="3",
                                    options=[
                                        me.SelectOption(label="1", value="1"),
                                        me.SelectOption(label="2", value="2"),
                                        me.SelectOption(label="3", value="3"),
                                        me.SelectOption(label="4", value="4"),
                                    ],
                                    on_selection_change=on_select_image_count,
                                    key="imagen_image_count",
                                    style=me.Style(width="155px"),
                                    disabled=state.image_model_name == cfg.MODEL_IMAGEN4_ULTRA,
                                )
                                me.checkbox(
                                    label="watermark",
                                    checked=True,
                                    disabled=True,
                                    key="imagen_watermark",
                                )
                                me.input(
                                    label="seed",
                                    disabled=True,
                                    key="imagen_seed",
                                )

                    # Image output
                    with me.box(style=_BOX_STYLE):
                        me.text("Output", style=me.Style(font_weight=500))
                        if state.is_loading:
                            with me.box(
                                style=me.Style(
                                    display="grid",
                                    justify_content="center",
                                    justify_items="center",
                                )
                            ):
                                me.progress_spinner()
                        if len(state.image_output) != 0:
                            with me.box(
                                style=me.Style(
                                    display="grid",
                                    justify_content="center",
                                    justify_items="center",
                                )
                            ):
                                # Generated images row
                                with me.box(
                                    style=me.Style(
                                        flex_wrap="wrap", display="flex", gap="15px"
                                    )
                                ):
                                    storage_client = get_storage_client()
                                    for _, img in enumerate(state.image_output):
                                        try:
                                            bucket_name, blob_name = img.replace("gs://", "").split("/", 1)
                                            bucket = storage_client.bucket(bucket_name)
                                            blob = bucket.blob(blob_name)
                                            # Use the service account associated with the Cloud Run service to sign the URL
                                            project_id = os.environ.get("PROJECT_ID")
                                            sa_email = f"sa-imagen-studio@{project_id}.iam.gserviceaccount.com"
                                            signed_url = blob.generate_signed_url(
                                                version="v4",
                                                expiration=datetime.timedelta(minutes=60),
                                                method="GET",
                                                service_account_email=sa_email,
                                                access_token=None,  # Use IAM to sign
                                            )
                                            me.image(
                                                src=signed_url,
                                                style=me.Style(
                                                    width="300px",
                                                    margin=me.Margin(top=10),
                                                    border_radius="35px",
                                                ),
                                            )
                                        except Exception as e:
                                            print(f"Error displaying image: {e}")

                                # SynthID notice
                                with me.box(
                                    style=me.Style(
                                        display="flex",
                                        flex_direction="row",
                                        align_items="center",
                                    )
                                ):
                                    svg_icon_component(
                                        svg="""<svg data-icon-name="digitalWatermarkIcon" viewBox="0 0 24 24" width="24" height="24" fill="none" aria-hidden="true" sandboxuid="2"><path fill="#3367D6" d="M12 22c-.117 0-.233-.008-.35-.025-.1-.033-.2-.075-.3-.125-2.467-1.267-4.308-2.833-5.525-4.7C4.608 15.267 4 12.983 4 10.3V6.2c0-.433.117-.825.35-1.175.25-.35.575-.592.975-.725l6-2.15a7.7 7.7 0 00.325-.1c.117-.033.233-.05.35-.05.15 0 .375.05.675.15l6 2.15c.4.133.717.375.95.725.25.333.375.717.375 1.15V10.3c0 2.683-.625 4.967-1.875 6.85-1.233 1.883-3.067 3.45-5.5 4.7-.1.05-.2.092-.3.125-.1.017-.208.025-.325.025zm0-2.075c2.017-1.1 3.517-2.417 4.5-3.95 1-1.55 1.5-3.442 1.5-5.675V6.175l-6-2.15-6 2.15V10.3c0 2.233.492 4.125 1.475 5.675 1 1.55 2.508 2.867 4.525 3.95z" sandboxuid="2"></path><path fill="#3367D6" d="M12 16.275c0-.68-.127-1.314-.383-1.901a4.815 4.815 0 00-1.059-1.557 4.813 4.813 0 00-1.557-1.06 4.716 4.716 0 00-1.9-.382c.68 0 1.313-.128 1.9-.383a4.916 4.916 0 002.616-2.616A4.776 4.776 0 0012 6.475c0 .672.128 1.306.383 1.901a5.07 5.07 0 001.046 1.57 5.07 5.07 0 001.57 1.046 4.776 4.776 0 001.901.383c-.672 0-1.306.128-1.901.383a4.916 4.916 0 00-2.616 2.616A4.716 4.716 0 0012 16.275z" sandboxuid="2"></path></svg>"""
                                    )

                                    me.text(
                                        text="images watermarked by SynthID",
                                        style=me.Style(
                                            padding=me.Padding(left=10, right=10, top=10, bottom=10),
                                            font_size="0.95em",
                                        ),
                                    )
                        else:
                            if state.is_loading:
                                me.text(
                                    text="generating images!",
                                    style=me.Style(
                                        display="grid",
                                        justify_content="center",
                                        padding=me.Padding.all(20),
                                    ),
                                )
                            else:
                                me.text(
                                    text="generate some images!",
                                    style=me.Style(
                                        display="grid",
                                        justify_content="center",
                                        padding=me.Padding.all(20),
                                    ),
                                )

                    # Image commentary
                    if len(state.image_output) != 0:
                        with me.box(style=_BOX_STYLE):
                            with me.box(
                                style=me.Style(
                                    display="flex",
                                    justify_content="space-between",
                                    gap=2,
                                    width="100%",
                                )
                            ):
                                with me.box(
                                    style=me.Style(
                                        flex_wrap="wrap",
                                        display="flex",
                                        flex_direction="row",
                                        # width="85%",
                                        padding=me.Padding(left=10, right=10, top=10, bottom=10),
                                    )
                                ):
                                    me.icon("assistant")
                                    me.text(
                                        "magazine editor",
                                        style=me.Style(font_weight=500),
                                    )
                                    me.markdown(
                                        text=state.image_commentary,
                                        style=me.Style(padding=me.Padding(left=15, right=15, top=15, bottom=15)),
                                    )

        footer()


def footer():
    """Creates the footer of the application"""
    with me.box(
        style=me.Style(
            # height="18px",
            padding=me.Padding(left=20, right=20, top=10, bottom=14),
            border=me.Border(
                top=me.BorderSide(width=1, style="solid", color="$ececf1")
            ),
            display="flex",
            justify_content="space-between",
            flex_direction="row",
            color="rgb(68, 71, 70)",
            letter_spacing="0.1px",
            line_height="14px",
            font_size=14,
            font_family="Google Sans",
        )
    ):
        me.html(
            "<a href='https://cloud.google.com/vertex-ai/generative-ai/docs/image/overview' target='_blank'>Imagen</a>",
        )
        me.html(
            "<a href='https://cloud.google.com/vertex-ai/generative-ai/docs/image/img-gen-prompt-guide' target='_blank'>Imagen Prompting Guide</a>"
        )
        me.html(
            "<a href='https://cloud.google.com/vertex-ai/generative-ai/docs/image/responsible-ai-imagen' target='_blank'>Imagen Responsible AI</a>"
        )


_BOX_STYLE = me.Style(
    flex_basis="max(480px, calc(50% - 48px))",
    background="#fff",
    border_radius=12,
    box_shadow=("0 3px 1px -2px #0003, 0 2px 2px #00000024, 0 1px 5px #0000001f"),
    padding=me.Padding(top=16, left=16, right=16, bottom=16),
    display="flex",
    flex_direction="column",
)

_BOX_STYLE_ROW = me.Style(
    flex_basis="max(480px, calc(50% - 48px))",
    background="#fff",
    border_radius=12,
    box_shadow=("0 3px 1px -2px #0003, 0 2px 2px #00000024, 0 1px 5px #0000001f"),
    padding=me.Padding(top=12, left=12, right=12, bottom=12),
    display="flex",
    flex_direction="row",
)

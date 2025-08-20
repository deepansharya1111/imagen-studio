# Copyright 2025 Google LLC
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

import mesop as me

from state.imagen_state import PageState
from config.imagen_models import get_imagen_model_config


@me.component
def advanced_controls():
    """Advanced image generation controls, driven by the selected model's configuration."""
    state = me.state(PageState)
    selected_config = get_imagen_model_config(state.image_model_name)

    if not selected_config:
        return

    with me.box(style=_BOX_STYLE):
        with me.box(
            style=me.Style(
                display="flex",
                justify_content="space-between",
                flex_wrap="wrap",
                gap="16px",
                width="100%",
            )
        ):
            if state.show_advanced:
                with me.content_button(on_click=on_click_advanced_controls):
                    with me.tooltip(message="Hide advanced controls"):
                        with me.box(style=me.Style(display="flex")):
                            me.icon("expand_less")
            else:
                with me.content_button(on_click=on_click_advanced_controls):
                    with me.tooltip(message="Show advanced controls"):
                        with me.box(style=me.Style(display="flex")):
                            me.icon("expand_more")

        if state.show_advanced:
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="row",
                    flex_wrap="wrap",
                    gap="16px",
                    margin=me.Margin(top=16),
                )
            ):
                me.input(
                    label="Negative prompt phrases",
                    on_blur=on_blur_image_negative_prompt,
                    value=state.image_negative_prompt_input,
                    key=str(state.image_negative_prompt_key),
                    style=me.Style(min_width="300px", flex_grow=2),
                )
                me.select(
                    label="Number of images",
                    value=str(state.imagen_image_count),
                    options=[
                        me.SelectOption(label=str(i), value=str(i))
                        for i in range(1, selected_config.max_samples + 1)
                    ],
                    on_selection_change=on_select_image_count,
                    style=me.Style(min_width="155px", flex_grow=1),
                )
                me.checkbox(
                    label="Watermark (SynthID)",
                    checked=state.imagen_watermark,
                    disabled=True,
                    key="imagen_watermark",
                )
                me.input(
                    label="Seed (0 for random)",
                    value=str(state.imagen_seed),
                    on_blur=on_blur_imagen_seed,
                    type="number",
                    style=me.Style(min_width="155px", flex_grow=1),
                )


def on_blur_image_negative_prompt(e: me.InputBlurEvent):
    """Negative image prompt blur event."""
    me.state(PageState).image_negative_prompt_input = e.value


def on_select_image_count(e: me.SelectSelectionChangeEvent):
    """Handles selection change for the number of images."""
    state = me.state(PageState)
    try:
        state.imagen_image_count = int(e.value)
    except ValueError:
        print(
            f"Invalid value for image count: {e.value}. Defaulting or handling error."
        )
        state.imagen_image_count = 4  # Or some other default / error state handling


def on_click_advanced_controls(e: me.ClickEvent):
    """Toggles visibility of advanced controls."""
    me.state(PageState).show_advanced = not me.state(PageState).show_advanced


def on_blur_imagen_seed(e: me.InputBlurEvent):
    """Handles blur event for the image seed input."""
    state = me.state(PageState)
    try:
        seed_value = int(e.value)
        state.imagen_seed = (
            seed_value if seed_value >= 0 else 0
        )  # Ensure seed is not negative
    except ValueError:
        state.imagen_seed = 0  # Default to 0 if input is not a valid integer
        print(f"Invalid seed value '{e.value}', defaulting to 0.")


_BOX_STYLE = me.Style(
    background=me.theme_var("surface"),
    border_radius=12,
    box_shadow=me.theme_var("shadow_elevation_2"),
    padding=me.Padding.all(16),
    display="flex",
    flex_direction="column",
    margin=me.Margin(bottom=28),
)

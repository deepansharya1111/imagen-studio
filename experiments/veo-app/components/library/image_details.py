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

# pyright: basic

"""A component for displaying media item details, including a carousel."""

import mesop as me

from common.metadata import MediaItem


@me.stateclass
class CarouselState:
    """State for the image carousel."""

    current_index: int = 0


def on_next(e: me.ClickEvent) -> None:
    """Event handler for the 'Next' button in the image carousel.

    Args:
        e: The Mesop click event.
    """
    state = me.state(CarouselState)
    state.current_index += 1


def on_prev(e: me.ClickEvent) -> None:
    """Event handler for the 'Previous' button in the image carousel.

    Args:
        e: The Mesop click event.
    """
    state = me.state(CarouselState)
    state.current_index -= 1


@me.component
def image_details(item: MediaItem) -> None:
    """A component that displays image details in a carousel.

    Args:
        item: The MediaItem to display.
    """
    state = me.state(CarouselState)
    num_images = len(item.gcs_uris)

    with me.box(
        style=me.Style(
            display="flex", flex_direction="column", align_items="center", gap=16
        )
    ):
        # Image display
        image_url = item.gcs_uris[state.current_index].replace(
            "gs://", "https://storage.mtls.cloud.google.com/"
        )
        me.image(
            src=image_url,
            style=me.Style(
                width="100%",
                height="auto",
                border_radius="8px",
            ),
        )

        # Carousel controls
        with me.box(
            style=me.Style(
                display="flex",
                align_items="center",
                justify_content="center",
                gap=16,
            )
        ):
            me.button(
                "Back",
                on_click=on_prev,
                disabled=state.current_index == 0,
            )
            me.text(f"{state.current_index + 1} / {num_images}")
            me.button(
                "Next",
                on_click=on_next,
                disabled=state.current_index >= num_images - 1,
            )

    if item.rewritten_prompt:
        me.text(f'Rewritten Prompt: "{item.rewritten_prompt}"')
    else:
        me.text(f"Prompt: '{item.prompt or 'N/A'}'")
    if item.negative_prompt:
        me.text(f"Negative Prompt: '{item.negative_prompt}'")
    if item.critique:
        me.text(f"Critique: {item.critique}")

    # Conditionally display VTO input images
    if item.raw_data and "virtual-try-on" in item.raw_data.get("model", ""):
        with me.box(style=me.Style(margin=me.Margin(top=16))):
            me.text(
                "Input Images",
                style=me.Style(font_weight="bold", margin=me.Margin(bottom=8)),
            )
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="row",
                    gap=16,
                    justify_content="center",
                )
            ):
                # Person Image
                person_gcs_uri = item.raw_data.get("person_image_gcs")
                if person_gcs_uri:
                    with me.box(
                        style=me.Style(
                            display="flex",
                            flex_direction="column",
                            align_items="center",
                            gap=4,
                        )
                    ):
                        me.text("Person Image")
                        person_url = person_gcs_uri.replace(
                            "gs://", "https://storage.mtls.cloud.google.com/"
                        )
                        me.image(
                            src=person_url,
                            style=me.Style(
                                width="200px", height="auto", border_radius="8px"
                            ),
                        )

                # Product Image
                product_gcs_uri = item.raw_data.get("product_image_gcs")
                if product_gcs_uri:
                    with me.box(
                        style=me.Style(
                            display="flex",
                            flex_direction="column",
                            align_items="center",
                            gap=4,
                        )
                    ):
                        me.text("Product Image")
                        product_url = product_gcs_uri.replace(
                            "gs://", "https://storage.mtls.cloud.google.com/"
                        )
                        me.image(
                            src=product_url,
                            style=me.Style(
                                width="200px", height="auto", border_radius="8px"
                            ),
                        )
    if item.comment == "product recontext":
        with me.box(style=me.Style(margin=me.Margin(top=16))):
            me.text(
                "Source Images",
                style=me.Style(font_weight="bold", margin=me.Margin(bottom=8)),
            )
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="row",
                    gap=16,
                    justify_content="center",
                )
            ):
                for uri in item.source_images_gcs:
                    me.image(
                        src=uri.replace(
                            "gs://", "https://storage.mtls.cloud.google.com/"
                        ),
                        style=me.Style(
                            width="100px", height="auto", border_radius="8px"
                        ),
                    )

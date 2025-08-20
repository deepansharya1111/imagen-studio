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
from typing import Callable

@me.component
def image_thumbnail(image_uri: str, index: int, on_remove: Callable):
    with me.box(style=me.Style(position="relative", width=100, height=100)):
        me.image(src=image_uri.replace("gs://", "https://storage.mtls.cloud.google.com/"), style=me.Style(width="100%", height="100%", border_radius=8, object_fit="cover"))
        with me.box(
            on_click=on_remove,
            key=str(index),
            style=me.Style(
                background="rgba(0, 0, 0, 0.5)",
                color="white",
                position="absolute",
                top=4,
                right=4,
                border_radius=50,
                padding=me.Padding.all(4),
                cursor="pointer",
            ),
        ):
            me.icon("close")

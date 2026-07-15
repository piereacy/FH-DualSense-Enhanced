# Third-Party Notices

## HorizonHaptics

The body-haptics effect selection, DualSense USB channel routing, and waveform
design in this project were informed by HorizonHaptics:

- Source: <https://github.com/haritha99ch/HorizonHaptics>
- Reference commit: `79fbe2fd7a56e21bd101867dbf14718f2e91ffab`
- Copyright: Copyright (c) 2026 Haritha Rathnayake
- License: MIT

HorizonHaptics is a development reference only. It is not started, embedded as
a separate application, or required at runtime.

```text
MIT License

Copyright (c) 2026 Haritha Rathnayake

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## vDS

The DualSense Bluetooth HD haptics report framing, 3 kHz stereo sample format,
sequence fields, and pacing design in this project were informed by vDS:

- Source: <https://github.com/hurryman2212/vds>
- Reference version: `0.3.0-rc7`
- Reference commit: `2d27ab0b2ea02e735cd3aa758cc5bf3d6e578534`
- Copyright: Copyright (c) 2026 Jihong Min
- License: MIT

FH-DualSense-Enhanced does not bundle the vDS daemon, virtual USB device,
filter driver, installer, or Opus runtime. It sends only its own telemetry-
generated haptic stream to the physical controller through the existing
hidapi connection.

```text
MIT License

Copyright (c) 2026 Jihong Min

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## DS5Dongle

vDS documents that part of its DualSense Bluetooth protocol work was derived
from DS5Dongle. FH-DualSense-Enhanced also used DS5Dongle to cross-check the
haptics-only packet layout:

- Source: <https://github.com/awalol/DS5Dongle>
- Reference commit: `ade9ea15b6fb1bf3f4fdc72da8c316234f32e0d0`
- Copyright: Copyright (c) 2026 awalol
- Repository license: MIT

No DS5Dongle firmware, USB descriptors, Bluetooth stack, audio codec, or
runtime component is bundled with FH-DualSense-Enhanced.

```text
MIT License

Copyright (c) 2026 awalol

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

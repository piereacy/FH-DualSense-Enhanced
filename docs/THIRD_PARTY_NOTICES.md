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

## ViGEmBus

The Windows EXE bundles the official ViGEmBus `1.22.0` installer for explicit,
offline installation when the Xbox App XInput bridge cannot connect to an
existing compatible bus:

- Source: <https://github.com/nefarius/ViGEmBus>
- Release: `1.22.0`
- Bundled installer size: `6,278,576` bytes
- SHA-256: `89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A`
- Copyright: Copyright (c) 2016-2020, Nefarius Software Solutions e.U.
- License: BSD 3-Clause

ViGEmBus is archived and no longer maintained upstream. FH-DualSense-Enhanced
does not automatically update, uninstall, or replace a compatible installed
driver. The installer runs only after user confirmation and Windows UAC.

```text
BSD 3-Clause License

Copyright (c) 2016-2020, Nefarius Software Solutions e.U.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## ViGEmClient

The Windows EXE bundles one x64 `ViGEmClient.dll` used through this project's
minimal `ctypes` wrapper:

- Source project: <https://github.com/nefarius/ViGEmClient>
- Asset source: <https://github.com/yannbouteiller/vgamepad/tree/3f910aa8bbde49a576683db74ad5e4a0879f8a80>
- Asset source version: `vgamepad 0.1.3`
- Bundled DLL size: `130,048` bytes
- SHA-256: `2BF0CB1D809039573C922737D298A1653D4DBC61408060FF45A9BCFDE82E97D2`
- Copyright: Copyright (c) 2018 Benjamin Höglinger-Stelzer
- License: MIT

ViGEmClient is archived and no longer maintained upstream. The `vgamepad`
Python runtime is not bundled or imported.

```text
MIT License

Copyright (c) 2018 Benjamin Höglinger-Stelzer

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

## vgamepad

The fixed `ViGEmClient.dll` described above was obtained from the `vgamepad`
`0.1.3` source distribution. No `vgamepad` Python code is bundled at runtime.

- Source: <https://github.com/yannbouteiller/vgamepad>
- Reference commit: `3f910aa8bbde49a576683db74ad5e4a0879f8a80`
- Copyright: Copyright (c) 2021 Yann Bouteiller
- License: MIT

```text
MIT License

Copyright (c) 2021 Yann Bouteiller

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

## DualSense Icons MOD

The Windows distribution bundles one verified controller-icon archive from
the DualSense Icons MOD and installs that same archive to FH6's normal and
HiRes controller-icon locations only after explicit user confirmation:

- Author: `@hotline1337`
- Source: <https://www.nexusmods.com/forzahorizon6/mods/2>
- Version: `2.1.1`
- Bundled archive size: `70,188` bytes
- SHA-256: `9677E50BF04276A9606956819D7760588EA7B986CFAFEBC70396F35630C53A61`

The project maintainer has stated that permission to bundle and redistribute
this MOD was obtained from the author. No separate general-purpose license
text was supplied with the archive, so this notice does not claim or grant
rights beyond that permission. Original game archives are not distributed;
they are backed up locally before installation and can be restored in-app.

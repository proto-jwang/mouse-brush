# Mouse Brush

Automated detection of brush-stimulation events in two-mouse experiment videos using Google Gemini AI.

## Demo

https://github.com/user-attachments/assets/3133d97f-0f17-4ca2-9beb-503e0e67b106

> Detected brush frames are highlighted in **red**; all other frames use white labels.

## What Does This Tool Do?

This tool automatically finds the exact video frame when a researcher brushes the back left foot of each mouse. It:

1. Takes your experiment videos as input
2. Converts each video to 1 frame per second (so every original frame is preserved)
3. Numbers each frame visibly in the top-right corner
4. Sends the video to Google's Gemini AI, which watches the video and identifies the exact frame where the brush makes full contact with each mouse's paw
5. Saves the result as a JSON file (left mouse = `L`, right mouse = `R`)
6. Optionally saves a new video with the detected frames highlighted in red

---

## Setup Instructions

Follow the section for your operating system. **Complete every step in order.**

---

### macOS

#### Step 1 — Install Homebrew (a package manager for macOS)

Homebrew lets you install software from the Terminal with simple commands.

1. Open **Terminal** (press `Command + Space`, type `Terminal`, press Enter)
2. Paste the following command and press Enter:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. Follow the on-screen prompts. It may ask for your Mac password — type it and press Enter (the cursor won't move while typing, that's normal).
4. When it finishes, verify it worked:

```bash
brew --version
```

You should see something like `Homebrew 4.x.x`.

---

#### Step 2 — Install Python

```bash
brew install python
```

Verify:

```bash
python3 --version
```

You should see `Python 3.x.x`.

---

#### Step 3 — Install ffmpeg

ffmpeg is a free tool that processes video files. This tool requires it.

```bash
brew install ffmpeg
```

This may take a few minutes. Verify:

```bash
ffmpeg -version
```

You should see a version number on the first line.

---

#### Step 4 — Install the Python library

```bash
pip3 install -U google-genai
```

---

#### Step 5 — Get a Gemini API Key

1. Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with your Google account
2. Click **"Create API key"**
3. Copy the key (it looks like a long string of letters and numbers)

---

#### Step 6 — Set your API Key

In Terminal, run the following (replace `YOUR_KEY` with the key you copied):

```bash
echo 'export GEMINI_API_KEY="YOUR_KEY"' >> ~/.zshrc
source ~/.zshrc
```

Verify it was saved:

```bash
echo $GEMINI_API_KEY
```

Your key should be printed.

---

### Linux (Ubuntu / Debian)

#### Step 1 — Install Python

Open a Terminal and run:

```bash
sudo apt update
sudo apt install python3 python3-pip
```

Verify:

```bash
python3 --version
```

---

#### Step 2 — Install ffmpeg

```bash
sudo apt install ffmpeg
```

Verify:

```bash
ffmpeg -version
```

---

#### Step 3 — Install the Python library

```bash
pip3 install -U google-genai
```

---

#### Step 4 — Get a Gemini API Key

1. Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with your Google account
2. Click **"Create API key"**
3. Copy the key

---

#### Step 5 — Set your API Key

```bash
echo 'export GEMINI_API_KEY="YOUR_KEY"' >> ~/.bashrc
source ~/.bashrc
```

Verify:

```bash
echo $GEMINI_API_KEY
```

---

### Windows

#### Step 1 — Install Python

1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/) and click **"Download Python 3.x.x"**
2. Run the downloaded installer
3. **Important:** On the first screen of the installer, check the box that says **"Add Python to PATH"** before clicking Install
4. Click **"Install Now"** and wait for it to finish

Verify: open **Command Prompt** (press `Windows + R`, type `cmd`, press Enter) and run:

```cmd
python --version
```

You should see `Python 3.x.x`.

---

#### Step 2 — Install ffmpeg

ffmpeg does not have a standard installer on Windows — follow these steps carefully:

1. Go to [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)
2. Under **"release builds"**, download `ffmpeg-release-essentials.zip`
3. Extract the zip file (right-click → "Extract All") — you can extract it to `C:\ffmpeg`
4. Inside the extracted folder, find the `bin` folder (e.g. `C:\ffmpeg\ffmpeg-7.x-essentials_build\bin`)
5. Add this `bin` folder to your system PATH:
   - Press `Windows + S` and search for **"Edit the system environment variables"**, click it
   - Click **"Environment Variables"** at the bottom
   - Under **"System variables"**, click on `Path` then click **"Edit"**
   - Click **"New"** and paste the full path to the `bin` folder (e.g. `C:\ffmpeg\ffmpeg-7.x-essentials_build\bin`)
   - Click **OK** on all windows to save

6. Close and reopen Command Prompt, then verify:

```cmd
ffmpeg -version
```

You should see a version number.

---

#### Step 3 — Install the Python library

In Command Prompt:

```cmd
pip install -U google-genai
```

---

#### Step 4 — Get a Gemini API Key

1. Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with your Google account
2. Click **"Create API key"**
3. Copy the key

---

#### Step 5 — Set your API Key

In Command Prompt (replace `YOUR_KEY` with your actual key):

```cmd
setx GEMINI_API_KEY "YOUR_KEY"
```

Close and reopen Command Prompt for the change to take effect. Verify:

```cmd
echo %GEMINI_API_KEY%
```

Your key should be printed.

---

## Download This Tool

1. Go to [https://github.com/proto-jwang/mouse-brush](https://github.com/proto-jwang/mouse-brush)
2. Click the green **"Code"** button → **"Download ZIP"**
3. Extract the ZIP to a folder, e.g. `C:\mouse-brush` (Windows) or `~/mouse-brush` (Mac/Linux)

---

## Running the Tool

Open Terminal (Mac/Linux) or Command Prompt (Windows) and navigate to the folder where you extracted the tool.

**Mac/Linux:**
```bash
cd ~/mouse-brush
```

**Windows:**
```cmd
cd C:\mouse-brush
```

### Basic usage

Place all your video files in a single folder (e.g. `videos/`). Then run:

**Mac/Linux:**
```bash
python3 pipeline.py \
    --input-dir  videos/ \
    --output-dir results/ \
    --visualize \
    --n-brushed-frames 5
```

**Windows:**
```cmd
python pipeline.py ^
    --input-dir  videos\ ^
    --output-dir results\ ^
    --visualize ^
    --n-brushed-frames 5
```

The tool will process every video in the `videos/` folder and save results to `results/`.

---

## Understanding the Output

For each video, a sub-folder is created under `results/`:

```
results/
  group_1/
    group_1_labeled.mp4    ← video with frame numbers burned in
    result.json            ← detected frame indices
    group_1_vis.mp4        ← visualization with red highlights (if --visualize)
```

**result.json** example:

```json
{
  "video": "group_1.mp4",
  "L": 42,
  "R": 87,
  "notes": "Clear contact visible for both sides."
}
```

- `L` — frame index (0-based) when the brush first fully contacts the **left mouse's** back left paw
- `R` — frame index for the **right mouse**
- `null` — means the mouse was never brushed, was brushed more than once, or the contact was ambiguous

---

## Options Reference

| Option | Default | Description |
|--------|---------|-------------|
| `--input-dir` | *(required)* | Folder containing your video files |
| `--output-dir` | *(required)* | Folder where results will be saved |
| `--visualize` | off | Also save a video with brush frames highlighted in red |
| `--n-brushed-frames` | `5` | How many frames after the brush contact to highlight |
| `--workers` | `4` | How many videos to process at the same time |
| `--model` | `gemini-2.5-pro` | Gemini model to use |

## Supported Video Formats

`.mp4`, `.avi`, `.mov`, `.mkv`, `.m4v`

---

## Notes

- Frame indices are **0-based** (the first frame is Frame 0).
- The AI only counts **full brush-paw contact** — partial contact or near-miss frames are ignored.
- Each mouse must be brushed **exactly once** per video. If a mouse is not brushed, or is brushed more than once, the result will be `null`.
- The tool automatically retries if the Gemini API is temporarily unavailable.

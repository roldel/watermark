# watermark
### Protect your documents before you share them with a customizable watermark


## How to use

### 1. Clone the repository
```sh
git clone https://github.com/roldel/watermark.git
cd watermark
```
### 2. Inside the cloned repository, setup a python docker container

```sh
sudo docker run -it -v $(pwd):/script -w /script python:slim bash
```

### 3. In the container, install dependencies

```sh
# apt dependencies
apt update && apt install -y ghostscript libjpeg-dev zlib1g-dev

# python dependencies
pip install pillow img2pdf PyPDF2 reportlab
```

### 4. Apply a watermark
You can now watermark any PDF or image file directly from the command line:
```sh
python watermark.py input_image/PDF_TestPage.pdf
```
By default this will:

- Save the result in output_image/

- Apply the text "Contract renewal Agency XYZ 010125"

- Use font size 20, angle 45°, opacity 0.15, density 100, and DPI 300


### 5. Customize the watermark

You can override any parameter at runtime:

```sh
python watermark.py input_image/PDF_TestPage.pdf \
    -o results \
    -t "Confidential" \
    -s 60 \
    -a 30 \
    -p 0.25 \
    -d 150 \
    --dpi 200
```

This will:

- Output to results/

- Apply watermark text "Confidential"

- Font size 60, rotated 30°

- Opacity 0.25

- Density 150

- Rasterization DPI 200






### 6. View available options

```sh
python watermark.py --help
```

Example output:

```sh
usage: watermark.py [-h] [-o OUTPUT_DIR] [-t TEXT] [-s SIZE] [-a ANGLE] [-p OPACITY] [-d DENSITY] [--dpi DPI] input_file

Apply a rasterized watermark to an image or PDF file.

positional arguments:
  input_file            Path to input image or PDF

options:
  -h, --help            show this help message and exit
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output directory (default: output_image)
  -t TEXT, --text TEXT  Watermark text (default: 'Contract renewal Agency XYZ 010125')
  -s SIZE, --size SIZE  Font size of watermark text (default: 20)
  -a ANGLE, --angle ANGLE
                        Rotation angle of watermark text (default: 45)
  -p OPACITY, --opacity OPACITY
                        Opacity of watermark text (0.0–1.0, default: 0.15)
  -d DENSITY, --density DENSITY
                        Density of watermark repetition (default: 100)
  --dpi DPI             DPI for Ghostscript rasterization (default: 300)
```
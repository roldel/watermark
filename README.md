# watermark
### Protect your documents before you share them with a customizable watermark


### How to use

Clone the repository
```sh
git clone https://github.com/roldel/watermark.git
cd watermark
```
Inside the cloned repository, setup a python docker container

```sh
sudo docker run -it -v $(pwd):/script -w /script python:slim bash
```

In the container, install dependencies

```sh
# apt dependencies
apt update && apt install -y ghostscript libjpeg-dev zlib1g-dev

# python dependencies
pip install pillow img2pdf PyPDF2 reportlab
```

Designate file to watermark and adjust main.py configuration parameters
```python
# --- Configuration ---

#INPUT_PATH = Path("input_image/PDF_TestPage.pdf")

OUTPUT_DIR = Path("output_image")
WATERMARK_TEXT = "Rent renewal"
WATERMARK_SIZE = 40
WATERMARK_ANGLE = 45
WATERMARK_OPACITY = 0.15
WATERMARK_DENSITY = 100

DPI_FOR_RASTERIZATION = 300
```
Apply the watermark

```sh
python main.py
```
# Upres QA tool
## Use cases
This tool was built to assess the quality of upscaled images in computer vision pipelines.

It allows fast visual comparison between ground-truth and output images, enabling:
- quick inspection of artifacts
- consistent quality validation
- efficient communication with stakeholders

## Features
- Define input and output folders for image comparisons
- Pressing I/O toggles input/output to easily compare the quality between both images (Ground-truth images are resized to match the output resolution for accurate comparison using the [Lanczos](https://en.wikipedia.org/wiki/Lanczos_algorithm) algorithm)
- Space bar to reset the canvas viewport
- Arrow keys to move through the images (buttons are also available)
- Multiple view methods: Toggle or Overlay with a selector to set the limit between both images
- Coming soon: difference map generator to standardize quality errors assessments

## Why did you make this tool?
I made a similar tool when I was working as Technical ML Product Manager in a computer vision start-up in 2017. 

There was no pipeline in place nor tools to assess the quality of our outputs, so I built something myself and used this opportunity to learn Python.

This tool has been very helpful in assessing the quality of our outputs easily by comparing them to our ground-truths. We also used in client meetings to show them our outputs and help have more visual arguments to present. 

I decided to create one again as it would be helpful in my current position too.


# Getting started

## How it works

- The tool compares images from two folders:
    - `ground-truth` (reference images)
    - `output` (upscaled or processed images)

- Images are matched using their **relative path and filename**
    - Both images must exist with the same name in both folders to be compared with the tool

## How to run

### Install dependencies

```bash
pip install customtkinter pillow numpy matplotlib scikit-image
```

### Run the tool

```bash
python main.py
```




# Screenshot
![Quick screengrab of the UI](img/screenshot.png)

# References and external links
- The image processing library used is [sci-kit-image](https://scikit-image.org)
- The images used as samples are taken from the Div2K library: https://data.vision.ee.ethz.ch/cvl/DIV2K/.

## Tech stack

- Python
- CustomTkinter (UI)
- Pillow (image processing)
- scikit-image (metrics and comparisons)
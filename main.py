import datetime
import hashlib
import os

from typing import List
from PIL import Image, ImageDraw, ImageFont


DATE_FROM = "20250101"
DATE_TO = "20251231"

SVG_SIZE = 32
MAX_BYTES = (SVG_SIZE * SVG_SIZE + 7) // 8

# A4 at 150 DPI is roughly 1754 x 1240 px in landscape
A4_WIDTH = 1754
A4_HEIGHT = 1240

DEFAULT_COLOUR = (40, 40, 40)
BG_COLOUR = (250, 250, 240)
SEASONAL_COLOURS = [
    (80, 120, 200),   # Winter
    (60, 180, 75),    # Spring
    (255, 200, 70),   # Summer
    (190, 100, 50),   # Autumn
]


def create_grid() -> List[List[int]]:
    return [[0 for _ in range(SVG_SIZE)] for _ in range(SVG_SIZE)]

def get_neighbors(grid: List[List[int]], x: int, y: int) -> int:
    count = 0
    for i in range(-1, 2):
        for j in range(-1, 2):
            if i == 0 and j == 0:
                continue
            new_x = (x + i + SVG_SIZE) % SVG_SIZE
            new_y = (y + j + SVG_SIZE) % SVG_SIZE
            count += grid[new_y][new_x]
    return count

def evolve_grid(grid: List[List[int]]) -> List[List[int]]:
    new_grid = create_grid()
    for y in range(SVG_SIZE):
        for x in range(SVG_SIZE):
            neighbors = get_neighbors(grid, x, y)
            if grid[y][x]:
                new_grid[y][x] = 1 if neighbors in [2, 3] else 0
            else:
                new_grid[y][x] = 1 if neighbors == 3 else 0
    return new_grid

def grid_to_png(
    grid: List[List[int]],
    active_colour: tuple = DEFAULT_COLOUR, 
    inactive_colour: tuple = BG_COLOUR,
    scale: int = 50
) -> Image.Image:
    width = SVG_SIZE * scale
    height = SVG_SIZE * scale
    
    image = Image.new('RGB', (width, height), inactive_colour)
    pixels = image.load()

    for y in range(SVG_SIZE):
        for x in range(SVG_SIZE):
            if grid[y][x]:
                for px in range(scale):
                    for py in range(scale):
                        pixels[x * scale + px, y * scale + py] = active_colour
    
    return image

def generate_png_art(
    input_text: str, 
    steps: int = 5, 
    active_colour: tuple = DEFAULT_COLOUR,
    inactive_colour: tuple = BG_COLOUR,
    scale: int = 50
) -> Image.Image:
    grid = create_grid()
    bytes_data = input_text.encode('utf-8')

    for i in range(MAX_BYTES):
        byte = bytes_data[i] if i < len(bytes_data) else 0
        for j in range(7, -1, -1):
            bit = (byte >> j) & 1
            bit_index = i * 8 + (7 - j)
            x = bit_index % SVG_SIZE
            y = bit_index // SVG_SIZE
            if y < SVG_SIZE and x < SVG_SIZE:
                grid[y][x] = bit

    current_grid = grid
    for _ in range(steps):
        current_grid = evolve_grid(current_grid)

    return grid_to_png(current_grid, active_colour, inactive_colour, scale)

def get_day_of_year(date: datetime.datetime) -> int:
    return date.timetuple().tm_yday

def interpolate_rgb(c1: tuple, c2: tuple, ratio: float) -> tuple:
    return tuple(
        int(v1 + (v2 - v1) * ratio)
        for v1, v2 in zip(c1, c2)
    )

def get_seasonal_colour(date: datetime.datetime) -> tuple:
    # Approximate day-of-year boundaries for each season
    year = date.year
    winter_start = datetime.datetime(year, 12, 21).timetuple().tm_yday
    spring_start = datetime.datetime(year, 3, 21).timetuple().tm_yday
    summer_start = datetime.datetime(year, 6, 21).timetuple().tm_yday
    autumn_start = datetime.datetime(year, 9, 21).timetuple().tm_yday
    
    day_of_year = get_day_of_year(date)
    
    if day_of_year < spring_start:
        # Winter → Spring
        prev_winter_start = winter_start - 365
        ratio = (day_of_year - prev_winter_start) / (spring_start - prev_winter_start)
        c1 = SEASONAL_COLOURS[0]  # Winter
        c2 = SEASONAL_COLOURS[1]  # Spring
        return interpolate_rgb(c1, c2, min(max(ratio, 0.0), 1.0))
    elif day_of_year < summer_start:
        # Spring → Summer
        ratio = (day_of_year - spring_start) / (summer_start - spring_start)
        c1 = SEASONAL_COLOURS[1]  # Spring
        c2 = SEASONAL_COLOURS[2]  # Summer
        return interpolate_rgb(c1, c2, min(max(ratio, 0.0), 1.0))
    elif day_of_year < autumn_start:
        # Summer → Autumn
        ratio = (day_of_year - summer_start) / (autumn_start - summer_start)
        c1 = SEASONAL_COLOURS[2]  # Summer
        c2 = SEASONAL_COLOURS[3]  # Autumn
        return interpolate_rgb(c1, c2, min(max(ratio, 0.0), 1.0))
    else:
        # Autumn → Winter
        ratio = (day_of_year - autumn_start) / (winter_start - autumn_start)
        c1 = SEASONAL_COLOURS[3]  # Autumn
        c2 = SEASONAL_COLOURS[0]  # Winter
        return interpolate_rgb(c1, c2, min(max(ratio, 0.0), 1.0))


def design_a4_landscape_card(
    pf_text: str,
    smaller_text: str,
    longer_text: str,
    signature: str,
    date_str: str,
    grid_image: Image.Image,
    active_colour: tuple = DEFAULT_COLOUR,
    bg_colour: tuple = BG_COLOUR
) -> Image.Image:
    card = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), bg_colour)
    draw = ImageDraw.Draw(card)

    font_large = ImageFont.truetype("PressStart2P-Regular.ttf", 100)
    font_medium = ImageFont.truetype("PressStart2P-Regular.ttf", 30)
    font_regular = ImageFont.truetype("Doto_Rounded-Black.ttf", 30)
    font_small = ImageFont.truetype("Doto_Rounded-Regular.ttf", 30)
    font_smallest = ImageFont.truetype("Doto_Rounded-Regular.ttf", 20)
    
    # Calculate left and right halves
    half = A4_WIDTH // 2
    
    # 1) Resize the grid image to fill 1/3 of page width
    grid_width = int(A4_WIDTH / 3)
    grid_height = grid_width
    grid_resized = grid_image.resize((grid_width, grid_height), resample=Image.NEAREST)
    grid_x = (half - grid_width) // 2
    grid_y = (A4_HEIGHT - grid_height) // 2 - 50
    card.paste(grid_resized, (grid_x, grid_y))
    
    # 2) PF text positioned 100px from left margin on right half, centered vertically
    pf_x = half
    pf_bbox = draw.textbbox((0, 0), pf_text, font=font_large)
    pf_text_height = pf_bbox[3] - pf_bbox[1]
    pf_y = grid_y + 90
    pf_text_pos = (pf_x, pf_y)
    
    # Draw the first part of the PF text
    draw.text(pf_text_pos, pf_text[:-4], fill="black", font=font_large, stroke_width=2)
    
    # Draw the last four letters with seasonal colours
    current_x = pf_x + draw.textlength(pf_text[:-4], font=font_large)
    for i, char in enumerate(pf_text[-4:]):
      colour = SEASONAL_COLOURS[i % len(SEASONAL_COLOURS)]
      draw.text((current_x, pf_y), char, fill=colour, font=font_large, stroke_width=2)
      current_x += draw.textlength(char, font=font_large)
    
    # 3) Smaller text below PF text, 40px from PF text
    smaller_text_x = pf_x
    smaller_text_y = pf_y + pf_text_height + 40
    smaller_text_pos = (smaller_text_x, smaller_text_y)
    draw.text(smaller_text_pos, smaller_text, fill="black", font=font_medium)

    # 4) Longer text below smaller text, 100px from smaller text
    longer_text_x = pf_x
    longer_text_y = smaller_text_y + 100
    for line in longer_text.split('\n'):
      draw.text((longer_text_x, longer_text_y), line, fill="black", font=font_regular)
      longer_text_y += draw.textbbox((0, 0), line, font=font_regular)[3] + 10  # Increase the spacing between lines

    # 5) Current date (below the grid)
    date_bbox = draw.textbbox((0, 0), date_str, font=font_small)
    date_text_width = date_bbox[2] - date_bbox[0]
    date_x = grid_x + (grid_width - date_text_width) // 2
    date_y = grid_y + grid_height + 40
    draw.text((date_x, date_y), date_str, fill=active_colour, font=font_small, stroke_width=1)

    # 6) Signature at the bottom-left, centered on x
    signature_bbox = draw.textbbox((0, 0), signature, font=font_smallest)
    signature_size = (signature_bbox[2] - signature_bbox[0], signature_bbox[3] - signature_bbox[1])
    signature_x = (A4_WIDTH - signature_size[0]) // 2
    signature_pos = (signature_x, A4_HEIGHT - signature_size[1] - 50)
    draw.text(signature_pos, signature, fill="black", font=font_smallest)

    # Draw the frame around the card
    frame_width = 10
    segment_length = 100
    colours = SEASONAL_COLOURS

    for i in range(0, A4_WIDTH, segment_length):
      colour = colours[(i // segment_length) % len(colours)]
      draw.rectangle(
        [i, 0, i + segment_length, frame_width],
        fill=colour
      )
      draw.rectangle(
        [i, A4_HEIGHT - frame_width, i + segment_length, A4_HEIGHT],
        fill=colour
      )

    for i in range(0, A4_HEIGHT, segment_length):
      colour = colours[(i // segment_length) % len(colours)]
      draw.rectangle(
        [0, i, frame_width, i + segment_length],
        fill=colour
      )
      draw.rectangle(
        [A4_WIDTH - frame_width, i, A4_WIDTH, i + segment_length],
        fill=colour
      )

    return card
  
def create_and_save_card(steps, date_obj=None):
    if date_obj is None:
        # Initial card
        date_str = ""
        active_colour = DEFAULT_COLOUR
        filename = "output/20250000.png"
    else:
        # Subsequent cards
        date_str = date_obj.strftime("%Y-%m-%d")
        active_colour = get_seasonal_colour(date_obj)
        filename = f'output/{date_obj.strftime(date_format)}.png'

    # Hash text: "PF 2025" hashed via SHA3-512
    hash_text = "PF 2025"
    hash_text = hashlib.sha3_512().hexdigest()

    grid_img = generate_png_art(
        hash_text,
        steps,
        active_colour,
        inactive_colour=BG_COLOUR,
        scale=40
    )

    a4_card = design_a4_landscape_card(
        pf_text="PF 2025",
        smaller_text="Enjoy the Game of Life!",
        longer_text=(
            "A festive generative art card inspired\n"
            "by the Game of Life cellular automaton.\n"
            "Starts with a SHA3-512 and UTF-8-hashed\n"
            "greeting, then evolves through the year."
        ),
        signature="INSPIRATION: Aleksandr Hovhannisyan | DESIGN: Michal Kolacek",
        date_str=date_str,
        grid_image=grid_img,
        active_colour=active_colour
    )
    a4_card.save(filename)
    return a4_card


if __name__ == "__main__":
    date_format = "%Y%m%d"

    date_from = datetime.datetime.strptime(DATE_FROM, date_format)
    date_to = datetime.datetime.strptime(DATE_TO, date_format)
    os.makedirs("output", exist_ok=True)

    frames = []

    # 1) Create the initial card (steps=0, no date)
    frames.append(create_and_save_card(0))

    # 2) Generate cards from date_from to date_to
    current_date = date_from
    while current_date <= date_to:
        steps = (current_date - date_from).days + 1
        frames.append(create_and_save_card(steps, current_date))
        current_date += datetime.timedelta(days=1)

    # 3) Optional GIF creation
    if frames:
        durations = [2000] + [20] * (len(frames) - 1)
        frames[0].save(
            "output/animation.gif",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0
        )

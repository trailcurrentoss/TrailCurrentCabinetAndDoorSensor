#!/usr/bin/env python3
"""
Generate KiCad footprint files for the TrailCurrent logo.

Converts the SVG logo from trailcurrent.com into two .kicad_mod files:
  - TrailCurrentLogo_Icon.kicad_mod  (mountain outline + filled trail + filled bolt)
  - TrailCurrentLogo_Text.kicad_mod  (TrailCurrent text)

The trail and lightning bolt are converted from stroked paths to filled polygon
outlines (stroke-to-path), preserving the smooth bezier curves of the original.
The mountain is rendered as an outline with gaps where filled shapes pass through.
"""

import math
import os
import uuid

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

ICON_TARGET_WIDTH_MM = 6.0
SVG_ICON_WIDTH = 38.0  # mountain base spans 0..38 in SVG coords
SCALE = ICON_TARGET_WIDTH_MM / SVG_ICON_WIDTH  # ~0.158 mm/SVG-unit

TRAIL_STROKE_SVG = 3.0
LIGHTNING_STROKE_SVG = 2.0
MOUNTAIN_OUTLINE_STROKE_MM = 0.15  # thin outline for the mountain

BEZIER_SEGMENTS = 16       # segments per bezier curve
ENDCAP_SEGMENTS = 6        # segments for semicircular end caps
CLEARANCE_MM = 0.12        # gap between mountain outline and filled shapes
SAMPLES_PER_SEG = 20       # proximity sampling density

TRANSLATE = (4, 8)

# SVG path data (before translate)
MOUNTAIN_PATH = [(0, 28), (12, 8), (18, 16), (28, 4), (38, 28)]

TRAIL_BEZIERS = [
    ((4, 26), (10, 22), (14, 24)),
    ((14, 24), (20, 27), (24, 22)),
    ((24, 22), (28, 17), (34, 20)),
]

LIGHTNING_PATH = [(30, 10), (33, 16), (29, 16), (32, 24)]

_FOOTPRINT_DIR = os.environ.get(
    "TRAILCURRENT_FOOTPRINT_DIR",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..",
        "TrailCurrentKiCADLibraries",
        "footprints",
    ),
)
OUTPUT_DIR = os.path.join(_FOOTPRINT_DIR, "TrailCurrentFootprints.pretty")


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def quadratic_bezier(p0, p1, p2, n_segments):
    """Tessellate a quadratic bezier curve into line segments."""
    points = []
    for i in range(n_segments + 1):
        t = i / n_segments
        mt = 1.0 - t
        x = mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0]
        y = mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]
        points.append((x, y))
    return points


def dist(a, b):
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


def lerp(a, b, t):
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def normal_vec(p1, p2):
    """Unit normal vector perpendicular to segment p1->p2 (left side)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-12:
        return (0.0, 1.0)
    return (-dy / length, dx / length)


def point_to_segment_dist(px, py, ax, ay, bx, by):
    """Minimum distance from point to line segment."""
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-12:
        return dist((px, py), (ax, ay))
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    return dist((px, py), (ax + t * dx, ay + t * dy))


def point_in_polygon(px, py, polygon):
    """Ray-casting point-in-polygon test."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and \
           (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# --------------------------------------------------------------------------
# Stroke-to-polygon conversion
# --------------------------------------------------------------------------

def offset_polyline_to_polygon(points, half_width, round_caps=True, round_joins=True):
    """Convert a stroked polyline into a filled polygon outline.

    Offsets the polyline by ±half_width to create left/right edges,
    adds semicircular end caps (matching stroke-linecap="round"),
    and rounded joins at interior vertices (matching stroke-linejoin="round").
    """
    if len(points) < 2:
        return points

    n = len(points)
    left = []
    right = []

    for i in range(n):
        if i == 0:
            nv = normal_vec(points[0], points[1])
            left.append((points[0][0] + nv[0] * half_width,
                         points[0][1] + nv[1] * half_width))
            right.append((points[0][0] - nv[0] * half_width,
                          points[0][1] - nv[1] * half_width))
        elif i == n - 1:
            nv = normal_vec(points[-2], points[-1])
            left.append((points[-1][0] + nv[0] * half_width,
                         points[-1][1] + nv[1] * half_width))
            right.append((points[-1][0] - nv[0] * half_width,
                          points[-1][1] - nv[1] * half_width))
        else:
            # Interior vertex: compute bisector normal
            n1 = normal_vec(points[i - 1], points[i])
            n2 = normal_vec(points[i], points[i + 1])
            dot = n1[0] * n2[0] + n1[1] * n2[1]

            if round_joins and dot < 0.95:
                # Angle is significant — add arc segments for rounded join
                angle1_l = math.atan2(n1[1], n1[0])
                angle2_l = math.atan2(n2[1], n2[0])
                # Ensure we sweep the short way
                da = angle2_l - angle1_l
                if da > math.pi:
                    da -= 2 * math.pi
                elif da < -math.pi:
                    da += 2 * math.pi

                arc_segs = max(2, int(abs(da) / (math.pi / 6)) + 1)
                for j in range(arc_segs + 1):
                    t = j / arc_segs
                    a = angle1_l + t * da
                    left.append((points[i][0] + math.cos(a) * half_width,
                                 points[i][1] + math.sin(a) * half_width))

                # Right side: opposite arc
                angle1_r = angle1_l + math.pi
                angle2_r = angle2_l + math.pi
                da_r = angle2_r - angle1_r
                if da_r > math.pi:
                    da_r -= 2 * math.pi
                elif da_r < -math.pi:
                    da_r += 2 * math.pi
                for j in range(arc_segs + 1):
                    t = j / arc_segs
                    a = angle1_r + t * da_r
                    right.append((points[i][0] + math.cos(a) * half_width,
                                  points[i][1] + math.sin(a) * half_width))
            else:
                # Nearly straight — use miter join
                bx = n1[0] + n2[0]
                by = n1[1] + n2[1]
                bl = math.sqrt(bx * bx + by * by)
                if bl > 1e-12:
                    bx /= bl
                    by /= bl
                    miter = 1.0 / max(0.5, (1 + dot) / 2)
                    hw = half_width * min(miter, 2.0)
                else:
                    bx, by = n1[0], n1[1]
                    hw = half_width

                left.append((points[i][0] + bx * hw,
                             points[i][1] + by * hw))
                right.append((points[i][0] - bx * hw,
                              points[i][1] - by * hw))

    # Build polygon: left path forward, end cap, right path reversed, start cap
    polygon = list(left)

    # End cap (semicircle at last point)
    if round_caps:
        last_nv = normal_vec(points[-2], points[-1])
        # Direction along the path at the end
        dx = points[-1][0] - points[-2][0]
        dy = points[-1][1] - points[-2][1]
        dl = math.sqrt(dx * dx + dy * dy)
        if dl > 1e-12:
            dx /= dl
            dy /= dl
        center = points[-1]
        start_angle = math.atan2(last_nv[1], last_nv[0])
        for j in range(1, ENDCAP_SEGMENTS):
            t = j / ENDCAP_SEGMENTS
            a = start_angle - t * math.pi  # sweep from left normal to right normal
            polygon.append((center[0] + math.cos(a) * half_width,
                            center[1] + math.sin(a) * half_width))

    polygon.extend(reversed(right))

    # Start cap (semicircle at first point)
    if round_caps:
        first_nv = normal_vec(points[0], points[1])
        center = points[0]
        start_angle = math.atan2(-first_nv[1], -first_nv[0])
        for j in range(1, ENDCAP_SEGMENTS):
            t = j / ENDCAP_SEGMENTS
            a = start_angle - t * math.pi
            polygon.append((center[0] + math.cos(a) * half_width,
                            center[1] + math.sin(a) * half_width))

    return polygon


# --------------------------------------------------------------------------
# Build paths in mm, centered at origin
# --------------------------------------------------------------------------

def build_paths_mm():
    """Build all element paths in mm coordinates, centered at origin."""
    # Mountain polygon
    mountain = [(x + TRANSLATE[0], y + TRANSLATE[1]) for x, y in MOUNTAIN_PATH]
    mountain_mm = [(x * SCALE, y * SCALE) for x, y in mountain]

    # Trail: tessellate beziers into polyline
    trail_pts = []
    for i, (p0, p1, p2) in enumerate(TRAIL_BEZIERS):
        p0t = (p0[0] + TRANSLATE[0], p0[1] + TRANSLATE[1])
        p1t = (p1[0] + TRANSLATE[0], p1[1] + TRANSLATE[1])
        p2t = (p2[0] + TRANSLATE[0], p2[1] + TRANSLATE[1])
        bpts = quadratic_bezier(p0t, p1t, p2t, BEZIER_SEGMENTS)
        if i == 0:
            trail_pts.extend(bpts)
        else:
            trail_pts.extend(bpts[1:])
    trail_mm = [(x * SCALE, y * SCALE) for x, y in trail_pts]

    # Lightning polyline
    lightning = [(x + TRANSLATE[0], y + TRANSLATE[1]) for x, y in LIGHTNING_PATH]
    lightning_mm = [(x * SCALE, y * SCALE) for x, y in lightning]

    # Center everything together
    all_pts = mountain_mm + trail_mm + lightning_mm
    all_x = [x for x, y in all_pts]
    all_y = [y for x, y in all_pts]
    cx = (min(all_x) + max(all_x)) / 2
    cy = (min(all_y) + max(all_y)) / 2

    return {
        "mountain": [(x - cx, y - cy) for x, y in mountain_mm],
        "trail": [(x - cx, y - cy) for x, y in trail_mm],
        "lightning": [(x - cx, y - cy) for x, y in lightning_mm],
    }


def build_icon_elements():
    """Build icon: mountain outline + filled trail + filled lightning."""
    raw = build_paths_mm()

    trail_half_w = (TRAIL_STROKE_SVG * SCALE) / 2
    lightning_half_w = (LIGHTNING_STROKE_SVG * SCALE) / 2

    # Convert stroked paths to filled polygon outlines
    trail_polygon = offset_polyline_to_polygon(raw["trail"], trail_half_w)
    lightning_polygon = offset_polyline_to_polygon(raw["lightning"], lightning_half_w)

    # Mountain as closed outline polyline
    mountain_outline = raw["mountain"] + [raw["mountain"][0]]

    # Gap the mountain outline where filled shapes are nearby
    trail_edges = [(trail_polygon[i], trail_polygon[(i + 1) % len(trail_polygon)])
                   for i in range(len(trail_polygon))]
    lightning_edges = [(lightning_polygon[i], lightning_polygon[(i + 1) % len(lightning_polygon)])
                      for i in range(len(lightning_polygon))]

    # Split mountain outline into sub-segments with gaps
    mountain_segments = split_outline_near_filled(
        mountain_outline, trail_polygon, lightning_polygon,
        trail_edges + lightning_edges, CLEARANCE_MM
    )

    return {
        "mountain_segments": mountain_segments,
        "mountain_stroke": MOUNTAIN_OUTLINE_STROKE_MM,
        "trail_polygon": trail_polygon,
        "lightning_polygon": lightning_polygon,
    }


def split_outline_near_filled(outline, trail_poly, lightning_poly,
                              all_edges, clearance):
    """Split outline polyline, gapping where it's inside or near filled shapes."""
    result = []
    current = []

    for i in range(len(outline) - 1):
        p1 = outline[i]
        p2 = outline[i + 1]
        seg_len = dist(p1, p2)
        if seg_len < 1e-9:
            continue

        for s in range(SAMPLES_PER_SEG + 1):
            t = s / SAMPLES_PER_SEG
            pt = lerp(p1, p2, t)

            # Check if point is inside either filled polygon
            inside = (point_in_polygon(pt[0], pt[1], trail_poly) or
                      point_in_polygon(pt[0], pt[1], lightning_poly))

            # Also check if point is near any filled polygon edge
            near_edge = False
            if not inside:
                for edge in all_edges:
                    d = point_to_segment_dist(
                        pt[0], pt[1],
                        edge[0][0], edge[0][1], edge[1][0], edge[1][1]
                    )
                    if d < clearance:
                        near_edge = True
                        break

            if inside or near_edge:
                if len(current) >= 2:
                    result.append(current)
                current = []
            else:
                current.append(pt)

    if len(current) >= 2:
        result.append(current)

    return result


# --------------------------------------------------------------------------
# KiCad .kicad_mod generation
# --------------------------------------------------------------------------

def gen_uuid():
    return str(uuid.uuid4())


def format_fp_poly(polygon, layer="F.SilkS"):
    """Format a filled polygon as fp_poly."""
    pts = "\n".join(
        f"\t\t\t(xy {x:.4f} {y:.4f})" for x, y in polygon
    )
    return f"""\t(fp_poly
\t\t(pts
{pts}
\t\t)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type solid)
\t\t)
\t\t(fill solid)
\t\t(layer "{layer}")
\t\t(uuid "{gen_uuid()}")
\t)"""


def format_fp_lines(points, stroke_width, layer="F.SilkS"):
    """Format a polyline as a series of fp_line elements."""
    lines = []
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        lines.append(f"""\t(fp_line
\t\t(start {x1:.4f} {y1:.4f})
\t\t(end {x2:.4f} {y2:.4f})
\t\t(stroke
\t\t\t(width {stroke_width:.4f})
\t\t\t(type solid)
\t\t)
\t\t(layer "{layer}")
\t\t(uuid "{gen_uuid()}")
\t)""")
    return lines


def generate_icon_footprint():
    elements = build_icon_elements()

    sections = []

    # Mountain outline segments (with gaps)
    for seg in elements["mountain_segments"]:
        sections.extend(format_fp_lines(seg, elements["mountain_stroke"]))

    # Trail: filled polygon
    sections.append(format_fp_poly(elements["trail_polygon"]))

    # Lightning: filled polygon
    sections.append(format_fp_poly(elements["lightning_polygon"]))

    return f"""(footprint "TrailCurrentLogo_Icon"
\t(version 20240108)
\t(generator "generate_logo_footprints.py")
\t(generator_version "2.0")
\t(layer "F.Cu")
\t(property "Reference" "LOGO"
\t\t(at 0 -4.5 0)
\t\t(unlocked yes)
\t\t(layer "F.SilkS")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.1)
\t\t\t)
\t\t)
\t)
\t(property "Value" "TrailCurrentLogo_Icon"
\t\t(at 0 4.5 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
\t(property "Footprint" ""
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
\t(property "Datasheet" ""
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
\t(property "Description" "TrailCurrent logo icon - mountain, trail, and lightning bolt"
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
\t(attr board_only exclude_from_pos_files exclude_from_bom)
{chr(10).join(sections)}
)
"""


def generate_text_footprint():
    text_size = 1.8
    text_thickness = 0.18

    return f"""(footprint "TrailCurrentLogo_Text"
\t(version 20240108)
\t(generator "generate_logo_footprints.py")
\t(generator_version "2.0")
\t(layer "F.Cu")
\t(property "Reference" "LOGO"
\t\t(at 0 -3 0)
\t\t(unlocked yes)
\t\t(layer "F.SilkS")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.1)
\t\t\t)
\t\t)
\t)
\t(property "Value" "TrailCurrentLogo_Text"
\t\t(at 0 3 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
\t(property "Footprint" ""
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
\t(property "Datasheet" ""
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
\t(property "Description" "TrailCurrent logo text"
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
\t(attr board_only exclude_from_pos_files exclude_from_bom)
\t(fp_text user "TrailCurrent"
\t\t(at 0 0 0)
\t\t(unlocked yes)
\t\t(layer "F.SilkS")
\t\t(uuid "{gen_uuid()}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size {text_size} {text_size})
\t\t\t\t(thickness {text_thickness})
\t\t\t\t(bold yes)
\t\t\t)
\t\t)
\t)
)
"""


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    icon_path = os.path.join(OUTPUT_DIR, "TrailCurrentLogo_Icon.kicad_mod")
    with open(icon_path, "w") as f:
        f.write(generate_icon_footprint())
    print(f"Generated: {icon_path}")

    text_path = os.path.join(OUTPUT_DIR, "TrailCurrentLogo_Text.kicad_mod")
    with open(text_path, "w") as f:
        f.write(generate_text_footprint())
    print(f"Generated: {text_path}")

    elements = build_icon_elements()
    print(f"\nMountain outline: {len(elements['mountain_segments'])} sub-segments")
    print(f"Trail polygon: {len(elements['trail_polygon'])} vertices")
    print(f"Lightning polygon: {len(elements['lightning_polygon'])} vertices")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import qrcode
from PIL import Image, ImageDraw
import segno

# Imports corrects pour l'output PNG stylé (qrcode 8.x)
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask


WHITE = "#fffffa"
TRANSPARENT_RGBA = (0, 0, 0, 0)

# ==========================
# Paramètres par défaut (éditables)
# Modifiez ces valeurs puis lancez simplement: python make_qr.py
# Chaque clé est aussi exposée en option CLI pour surcharger au besoin.
#
# data: l'URL encodée (courte recommandée). Exemple: "http://localhost:8000/x".
# logo: chemin d'un PNG à centrer (fond transparent conseillé). Laissez vide pour aucun logo.
# png/svg: chemins de sortie.
# max_version: limite de version QR pour éviter trop de densité (1..40). 5 conseillé si possible.
# card: si True, ajoute une carte arrondie blanche semi-transparente sous le QR (utile sur fond clair/chargé).
# box_size: taille d'un module (pixel) pour le PNG (plus grand = image plus nette et plus grande).
# no_plaque: si True, désactive la plaque blanche sous le logo (fond 100% transparent conservé).
DEFAULTS = {
    "data": "http://localhost:8000/x",
    "logo": "assets/logo.png",
    "png": "out/qr_white.png",
    "svg": "out/qr_white.svg",
    "max_version": 20,
    "card": False,
    "box_size": 60,
    "no_plaque": True,
    # Bordure (quiet zone) en modules; augmentez (6-8) pour un rendu visuellement moins chargé
    "border": 2,
    # Échelle du logo par rapport à la largeur du QR (0.18 à 0.22 conseillé)
    "logo_scale": 0.30,
    # Ratio de marge autour du logo sur la plaque (0.08 à 0.12)
    "logo_pad": 0.40,
    # Arrondi des yeux (finder patterns) : proportion du rayon vs taille de l'œil (7 modules)
    # 0.0 = angle vif, 0.5 = coin très arrondi
    "eye_radius_scale": 0.10,
    # Crée une zone circulaire vide (transparente) autour du logo
    # True pour activer, le rayon est proportionnel à la largeur du QR
    "logo_cutout": True,
    # Proportion du rayon du cutout vs largeur du QR (ex: 0.10 ⇒ diamètre ~20%)
    "cutout_radius_scale": 0.10,
    # Densité: forcer une version (0 = auto) et choisir le niveau d'erreur (h/q/m/l)
    "force_version": 3,
    "error_level": "q",
    # Micro QR (moins de modules si les données tiennent). PNG sans arrondis ni logo.
    "micro": False,
}


@dataclass
class Args:
    data: str
    logo_path: Path
    png_out: Path
    svg_out: Path
    max_version: int
    card: bool
    box_size: int
    no_plaque: bool
    border: int
    logo_scale: float
    logo_pad: float
    eye_radius_scale: float
    logo_cutout: bool
    cutout_radius_scale: float
    force_version: int
    error_level: str
    micro: bool


def parse_args(argv: list[str]) -> Args:
    parser = argparse.ArgumentParser(
        description="Génère un QR code blanc, fond transparent, logo centré."
    )
    parser.add_argument(
        "--data",
        default=DEFAULTS["data"],
        help="Données à encoder (URL courte recommandée)",
    )
    parser.add_argument(
        "--logo", default=DEFAULTS["logo"], help="Chemin du logo centré (PNG)"
    )
    parser.add_argument("--png", default=DEFAULTS["png"], help="Chemin de sortie PNG")
    parser.add_argument("--svg", default=DEFAULTS["svg"], help="Chemin de sortie SVG")
    parser.add_argument(
        "--max-version",
        type=int,
        default=DEFAULTS["max_version"],
        help="Version QR maximale pour limiter la densité",
    )
    parser.add_argument(
        "--card",
        action="store_true",
        default=DEFAULTS["card"],
        help="Ajoute une carte arrondie blanche semi-transparente sous le QR",
    )
    parser.add_argument(
        "--box-size",
        type=int,
        default=DEFAULTS["box_size"],
        help="Taille d'un module en pixels pour le PNG (plus grand = plus net)",
    )
    parser.add_argument(
        "--no-plaque",
        action="store_true",
        default=DEFAULTS["no_plaque"],
        help="Désactive la plaque blanche arrondie sous le logo (fond 100% transparent)",
    )
    parser.add_argument(
        "--border",
        type=int,
        default=DEFAULTS["border"],
        help="Quiet zone en modules (par défaut 4; 6-8 pour visuel plus aéré)",
    )
    parser.add_argument(
        "--logo-scale",
        type=float,
        default=DEFAULTS["logo_scale"],
        help="Taille du logo par rapport à la largeur du QR (0.18–0.22)",
    )
    parser.add_argument(
        "--logo-pad",
        type=float,
        default=DEFAULTS["logo_pad"],
        help="Marge autour du logo sur la plaque (0.08–0.12)",
    )
    parser.add_argument(
        "--eye-radius-scale",
        type=float,
        default=DEFAULTS["eye_radius_scale"],
        help="Rayon des coins arrondis des yeux en proportion de 7 modules (0–0.5)",
    )
    parser.add_argument(
        "--logo-cutout",
        action="store_true",
        default=DEFAULTS["logo_cutout"],
        help="Crée un disque vide autour du logo (zone transparente)",
    )
    parser.add_argument(
        "--cutout-radius-scale",
        type=float,
        default=DEFAULTS["cutout_radius_scale"],
        help="Rayon du cutout en proportion de la largeur du QR (ex: 0.13)",
    )
    parser.add_argument(
        "--force-version",
        type=int,
        default=DEFAULTS["force_version"],
        help="Forcer la version du QR (0 = auto). Échoue si données trop longues.",
    )
    parser.add_argument(
        "--error-level",
        type=str,
        choices=["h", "q", "m", "l"],
        default=DEFAULTS["error_level"],
        help="Niveau de correction d'erreur (h/q/m/l). H recommandé avec logo.",
    )
    parser.add_argument(
        "--micro",
        action="store_true",
        default=DEFAULTS["micro"],
        help="Génère un Micro QR (moins dense si les données tiennent). Pas de logo/arrondis.",
    )
    ns = parser.parse_args(argv)
    return Args(
        data=ns.data,
        logo_path=Path(ns.logo) if ns.logo else Path(""),
        png_out=Path(ns.png),
        svg_out=Path(ns.svg),
        max_version=ns.__dict__["max_version"],
        card=ns.card,
        box_size=ns.__dict__["box_size"],
        no_plaque=ns.__dict__["no_plaque"],
        border=ns.__dict__["border"],
        logo_scale=ns.__dict__["logo_scale"],
        logo_pad=ns.__dict__["logo_pad"],
        eye_radius_scale=ns.__dict__["eye_radius_scale"],
        logo_cutout=ns.__dict__["logo_cutout"],
        cutout_radius_scale=ns.__dict__["cutout_radius_scale"],
        force_version=ns.__dict__["force_version"],
        error_level=ns.__dict__["error_level"],
        micro=ns.__dict__["micro"],
    )


def ensure_out_dir(path: Path) -> None:
    out_dir = path.parent
    out_dir.mkdir(parents=True, exist_ok=True)


def estimate_min_version(data: str) -> int:
    """Estime grossièrement la version nécessaire pour une URL ASCII.

    Cette estimation est volontairement simple pour émettre un warning si > max_version.
    Basé sur la capacité approx. pour niveau H (~30% redondance). Version 5 H ~ 68 char alphanum.
    """
    length = len(data)
    thresholds = [
        (1, 9),  # V1-H ~ 9
        (2, 16),  # V2-H ~ 16
        (3, 26),  # V3-H ~ 26
        (4, 36),  # V4-H ~ 36
        (5, 68),  # V5-H ~ 68
        (6, 86),
        (7, 108),
        (8, 124),
        (9, 157),
        (10, 189),
    ]
    for version, capacity in thresholds:
        if length <= capacity:
            return version
    return 10


def warn_contrast(card: bool) -> None:
    msg = (
        "Attention: avant-plan blanc. Assurez un fond sombre pour un bon contraste. "
        "Sinon utilisez l'option --card pour poser une carte sous le QR."
    )
    if not card:
        print(msg)


def draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    radius: int,
    fill: Tuple[int, int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def compose_logo_with_plaque(
    base: Image.Image,
    logo_path: Path,
    use_plaque: bool = True,
    logo_scale: float = DEFAULTS["logo_scale"],
    logo_pad_ratio: float = DEFAULTS["logo_pad"],
) -> Image.Image:
    """Centre le logo avec une plaque blanche arrondie derrière (opacité ~0.92)."""
    if not logo_path.exists():
        print(f"[WARN] Logo non trouvé: {logo_path}. Le QR sera généré sans logo.")
        return base

    qr_w, qr_h = base.size
    target_w = int(qr_w * float(logo_scale))
    target_h = target_w

    try:
        logo = Image.open(logo_path).convert("RGBA")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[WARN] Impossible d'ouvrir le logo: {exc}. QR sans logo.")
        return base

    logo.thumbnail((target_w, target_h), Image.LANCZOS)
    lw, lh = logo.size

    pad = int(max(lw, lh) * float(logo_pad_ratio))
    plaque_w, plaque_h = lw + 2 * pad, lh + 2 * pad

    if use_plaque:
        plaque = Image.new("RGBA", (plaque_w, plaque_h), TRANSPARENT_RGBA)
        draw = ImageDraw.Draw(plaque)
        radius = int(min(plaque_w, plaque_h) * 0.25)
        white_with_alpha = (255, 255, 255, int(255 * 0.92))
        draw_rounded_rect(
            draw, (0, 0, plaque_w, plaque_h), radius=radius, fill=white_with_alpha
        )
        plaque.paste(logo, (pad, pad), mask=logo)
        px = (qr_w - plaque_w) // 2
        py = (qr_h - plaque_h) // 2
        base.alpha_composite(plaque, dest=(px, py))
        return base
    else:
        # Pas de plaque : coller le logo directement, centré
        px = (qr_w - lw) // 2
        py = (qr_h - lh) // 2
        base.alpha_composite(logo, dest=(px, py))
        return base


def make_png(args: Args) -> Path:
    ensure_out_dir(args.png_out)

    # Correction d'erreur paramétrable
    err_map = {
        "h": qrcode.constants.ERROR_CORRECT_H,
        "q": qrcode.constants.ERROR_CORRECT_Q,
        "m": qrcode.constants.ERROR_CORRECT_M,
        "l": qrcode.constants.ERROR_CORRECT_L,
    }
    error_corr = err_map.get(args.error_level.lower(), qrcode.constants.ERROR_CORRECT_H)

    qr = qrcode.QRCode(
        version=(None if args.force_version in (0, None) else int(args.force_version)),
        error_correction=error_corr,
        box_size=args.box_size,
        border=args.border,
    )
    qr.add_data(args.data)
    try:
        qr.make(fit=(args.force_version in (0, None)))
    except Exception as exc:
        raise RuntimeError(
            "Données trop longues pour la version forcée; augmentez force_version ou utilisez une URL plus courte."
        ) from exc

    # Vérif densité vs max_version (estimation)
    est_version = estimate_min_version(args.data)
    if est_version > args.max_version:
        print(
            f"[AVERTISSEMENT] Données longues (estimation version ~{est_version} > max {args.max_version}). "
            "Le QR peut devenir dense. Utilisez un lien plus court."
        )

    # Image arrondie, fond transparent
    # Convertit la couleur hex WHITE en (r,g,b,255)
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        s = hex_color.strip().lstrip("#")
        if len(s) == 3:
            s = "".join([c * 2 for c in s])
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return r, g, b

    fr, fg, fb = _hex_to_rgb(WHITE)
    # Sans RoundedEyeDrawer (non dispo dans cette version). On post-traite les yeux.
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(0, 0, 0, 0),
            front_color=(fr, fg, fb, 255),
        ),
    )

    # StyledPilImage renvoie un wrapper avec get_image()
    pil_img = img.get_image() if hasattr(img, "get_image") else img
    pil_img = pil_img.convert("RGBA")

    # Post-traitement pour arrondir visuellement les coins des yeux (finder patterns)
    # On découpe l'alpha aux coins des 3 yeux selon un masque à bords arrondis
    if args.eye_radius_scale and args.eye_radius_scale > 0:
        w, h = pil_img.size
        module_px = args.box_size
        eye_modules = 7  # motif des yeux fait 7x7 modules
        eye_px = eye_modules * module_px
        radius = int(eye_px * float(args.eye_radius_scale))
        # positions des 3 yeux: haut-gauche, haut-droit, bas-gauche (hors quiet zone)
        border_px = args.border * module_px
        corners = [
            (border_px, border_px),
            (w - border_px - eye_px, border_px),
            (border_px, h - border_px - eye_px),
        ]
        r_chan, g_chan, b_chan, a_chan = pil_img.split()
        for x0, y0 in corners:
            # masque des coins à effacer: 255 = effacer (alpha=0), 0 = conserver
            erase_mask = Image.new("L", (eye_px, eye_px), 255)
            mdraw = ImageDraw.Draw(erase_mask)
            mdraw.rounded_rectangle([0, 0, eye_px, eye_px], radius=radius, fill=0)
            # appliquer sur canal alpha
            a_chan.paste(0, box=(x0, y0, x0 + eye_px, y0 + eye_px), mask=erase_mask)
        pil_img = Image.merge("RGBA", (r_chan, g_chan, b_chan, a_chan))

    if args.card:
        # Carte arrondie blanche semi-transparente sous le QR
        w, h = pil_img.size
        card_pad = int(min(w, h) * 0.06)
        card_img = Image.new(
            "RGBA", (w + 2 * card_pad, h + 2 * card_pad), TRANSPARENT_RGBA
        )
        draw = ImageDraw.Draw(card_img)
        radius = int(min(card_img.size) * 0.10)
        card_color = (255, 255, 255, int(255 * 0.85))
        draw_rounded_rect(
            draw, (0, 0, card_img.width, card_img.height), radius, card_color
        )
        card_img.alpha_composite(pil_img, dest=(card_pad, card_pad))
        pil_img = card_img

    # Créer le cutout AVANT d'apposer le logo pour que le logo reste visible au-dessus
    if args.logo_cutout:
        w, h = pil_img.size
        # Adapter le cutout pour qu'il couvre au moins le logo (60% de sa largeur)
        base_radius = int(min(w, h) * float(args.cutout_radius_scale))
        # Vise un cutout au moins égal au demi-largeur du logo (ajustable 0.52–0.65)
        logo_radius_target = int(min(w, h) * float(args.logo_scale) * 0.52)
        radius = max(base_radius, logo_radius_target)
        cx, cy = w // 2, h // 2
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
        # Effacer (mettre alpha à 0) dans le disque
        r, g, b, a = pil_img.split()
        a.paste(0, (0, 0, w, h), mask)
        pil_img = Image.merge("RGBA", (r, g, b, a))

    pil_img = compose_logo_with_plaque(
        pil_img,
        args.logo_path,
        use_plaque=not args.no_plaque,
        logo_scale=args.logo_scale,
        logo_pad_ratio=args.logo_pad,
    )

    pil_img.save(args.png_out, format="PNG")
    return args.png_out


def make_svg(args: Args) -> Path:
    ensure_out_dir(args.svg_out)
    q = segno.make(args.data, error=args.error_level, micro=args.micro)
    q.save(
        args.svg_out,
        scale=10,
        border=args.border,
        light=None,
        dark=WHITE,
    )
    return args.svg_out


def make_micro_png(args: Args) -> Path:
    """Génère un PNG Micro QR via segno (fond transparent, blanc, sans logo)."""
    ensure_out_dir(args.png_out)
    q = segno.make(args.data, error=args.error_level, micro=True)
    q.save(
        args.png_out,
        scale=max(8, args.box_size // 2),
        border=args.border,
        light=None,
        dark=WHITE,
        kind="png",
    )
    return args.png_out


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    warn_contrast(args.card)

    try:
        if args.micro:
            png_path = make_micro_png(args)
            svg_path = make_svg(args)
        else:
            png_path = make_png(args)
            svg_path = make_svg(args)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[ERREUR] Échec de génération: {exc}")
        return 1

    print(f"PNG généré: {png_path}")
    print(f"SVG généré: {svg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

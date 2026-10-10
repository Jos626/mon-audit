"""Fabrique les icônes de l'application installable (Perform).

Un carré marine aux coins arrondis, un disque vert, une coche blanche : « ton audit est passé ».
On les régénère avec : python3 fabriquer-icones.py

LEÇON (10/10/2026) : le premier jet n'avait pas d'icône du tout — la page s'installait sans image,
ce qui ne ressemble pas à une application. Les icônes sont donc des fichiers du projet, versionnés
avec le reste, et pas des images récupérées ailleurs.
"""
import os
from PIL import Image, ImageDraw

ICI = os.path.dirname(os.path.abspath(__file__))
FOND, VERT, BLANC = (15, 23, 42), (34, 197, 94), (255, 255, 255)


def dessine(cote, marge_relative=0.0):
    """marge_relative > 0 : la version « masquable », dont le sujet tient dans le cercle de découpe."""
    img = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = int(cote * marge_relative)
    d.rounded_rectangle([m, m, cote - 1 - m, cote - 1 - m], radius=int(cote * 0.22), fill=FOND)
    centre, r = cote // 2, int(cote * 0.30)
    d.ellipse([centre - r, centre - r, centre + r, centre + r], fill=VERT)
    e = int(cote * 0.055)
    d.line([(cote * 0.35, cote * 0.51), (cote * 0.46, cote * 0.63)], fill=BLANC, width=e, joint="curve")
    d.line([(cote * 0.46, cote * 0.63), (cote * 0.66, cote * 0.39)], fill=BLANC, width=e, joint="curve")
    return img


if __name__ == "__main__":
    for cote, nom, marge in ((192, "icone-192.png", 0.0), (512, "icone-512.png", 0.0),
                             (512, "icone-masquable-512.png", 0.14),
                             (180, "icone-apple-180.png", 0.0), (32, "iparv.png", 0.0)):
        chemin = os.path.join(ICI, nom)
        dessine(cote, marge).save(chemin, "PNG", optimize=True)
        print(f"{nom:26} {cote}×{cote} · {os.path.getsize(chemin)/1024:.1f} Ko")

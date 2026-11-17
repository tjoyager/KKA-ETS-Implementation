"""A proper sealed cardboard carton for the [1] placement tool."""
from ursina import Entity, Vec3, color
from ursina.shaders import lit_with_shadows_shader


def make_cardboard_box(parent, position):
    # One box collider on the solid body. Details never intercept selection rays.
    box = Entity(parent=parent, model='cube', position=position,
                 scale=Vec3(.82, .70, .82), color=color.rgb32(175, 125, 73),
                 collider='box', shader=lit_with_shadows_shader)
    def part(pos, scale, rgb):
        return Entity(parent=box, model='cube', position=pos, scale=scale,
                      color=color.rgb32(*rgb), collider=None,
                      shader=lit_with_shadows_shader)
    # Two top flaps and a slightly darker center seam.
    part((-.251,.502,0),(.494,.006,.988),(198,151,94))
    part(( .251,.502,0),(.494,.006,.988),(189,141,85))
    part((0,.507,0),(.014,.004,.99),(103,73,43))
    # Kraft tape seals the top, folds over both ends and wraps underneath.
    tape=(215,179,119)
    part((0,.512,0),(.155,.008,1.015),tape)
    for z in (-.504,.504):
        part((0,.28,z),(.155,.44,.008),tape)
        part((-.494,0,z),(.009,.98,.008),(145,99,55))
        part(( .494,0,z),(.009,.98,.008),(145,99,55))
    # Paper shipping label with a geometric barcode on the front face.
    part((.24,.04,-.509),(.30,.25,.008),(230,221,198))
    for i in range(11):
        part((.114+i*.022,.012,-.515),(.009 if i%3 else .015,.105,.004),(62,60,52))
    part((.24,.115,-.515),(.23,.014,.004),(90,85,71))
    part((.20,.085,-.515),(.15,.009,.004),(112,105,86))
    # Two upright handling arrows on the side.
    for z in (-.16,.12):
        part((.507,-.10,z),(.008,.20,.022),(91,68,42))
        for angle in (-45,45):
            arrow=part((.509,.015,z+(.024 if angle>0 else -.024)),(.008,.075,.018),(91,68,42))
            arrow.rotation_x=angle
    return box

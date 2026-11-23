"""Model-based replacement for the green pole markers inside the warehouse."""
import math
from pathlib import Path
from ursina import Entity, Vec3, color, time
from ursina.shaders import lit_with_shadows_shader, unlit_shader
from src.config import grid_to_world


class InteriorChargingStation(Entity):
    def __init__(self, manager, dock):
        parent = manager.scene if isinstance(getattr(manager, 'scene', None), Entity) else None
        super().__init__(parent=parent, position=grid_to_world(*dock, .025),
                         name='interior_charging_station', collider=None)
        self.manager=manager
        self.dock=dock
        # Back the cabinet toward an existing obstacle when possible.
        for dx,dy,yaw in ((0,-1,0),(-1,0,90),(0,1,180),(1,0,-90)):
            if not manager.graph.is_walkable(dock[0]+dx,dock[1]+dy):
                self.rotation_y=yaw
                break
        root=Path(__file__).resolve().parents[2]
        paths=[root/'assets/models/docking-station.obj',root/'assets/model/docking-station.obj']
        path=next((p for p in paths if p.is_file()),None)
        if path is None:raise FileNotFoundError('docking-station.obj is missing')
        self.model_body=Entity(parent=self,model=path.relative_to(root).as_posix(),
            position=(0,0,-.08),scale=(.55,.82,.49),collider=None,shader=lit_with_shadows_shader)
        # Outer geometry stays within the original 0.9 x 0.9 station cell.
        Entity(parent=self,model='cube',position=(0,-.012,0),scale=(.89,.018,.89),
               color=color.rgb32(39,61,63),collider=None,shader=lit_with_shadows_shader)
        for x in (-.425,.425):
            Entity(parent=self,model='cube',position=(x,.006,.08),scale=(.022,.008,.66),
                   color=color.rgb32(89,203,167),collider=None,shader=unlit_shader)
        Entity(parent=self,model='cube',position=(0,.008,.405),scale=(.85,.008,.025),
               color=color.rgb32(89,203,167),collider=None,shader=unlit_shader)
        # Cover the original coplanar display with a clean screen and charge bars.
        Entity(parent=self.model_body,model='cube',position=(-.017,.886,-.370),
               scale=(.46,.31,.025),color=color.rgb32(17,34,44),collider=None,shader=unlit_shader)
        self.bars=[]
        for i in range(5):
            self.bars.append(Entity(parent=self.model_body,model='cube',
                position=(-.173+i*.078,.88,-.349),scale=(.055,.12,.012),
                color=color.rgb32(89,203,167),collider=None,shader=unlit_shader))
        Entity(parent=self,model='cube',position=(0,1.06,-.36),scale=(.34,.07,.08),
               color=color.rgb32(35,51,58),collider=None,shader=lit_with_shadows_shader)
        self.lamp=Entity(parent=self,model='cube',position=(0,1.06,-.31),scale=(.26,.027,.015),
                         color=color.rgb32(89,203,167),collider=None,shader=unlit_shader)

    def update(self):
        charging=[r for r in (self.manager.robot_alpha,self.manager.robot_beta)
                  if getattr(r.state,'name','')=='CHARGING'
                  and getattr(r,'emergency_dock',None)==self.dock]
        if charging:
            battery=min(r.battery for r in charging)
            pulse=.65+.35*math.sin(time.time()*4)**2
            self.lamp.color=color.rgb32(int(90*pulse),int(230*pulse),int(167*pulse))
            for i,bar in enumerate(self.bars):
                bar.color=color.rgb32(*((89,203,167) if battery>i*20 else (36,53,60)))
        else:
            self.lamp.color=color.rgb32(89,203,167)
            # Idle screen is dim, rather than displaying a fictitious battery level.
            for bar in self.bars:bar.color=color.rgb32(36,65,64)


def build_charging_station(scene=None):
    """Fallback / alias helper agar sinkron dengan charging_station.py."""
    from src.environment.charging_station import build_charging_station as _bcs
    return _bcs(scene)


__all__ = ["InteriorChargingStation", "build_charging_station"]


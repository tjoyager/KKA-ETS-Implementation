"""Twin charging bays using the project's docking-station OBJ and its materials."""
import math
from pathlib import Path
from ursina import Entity, Vec3, color, destroy, time
from ursina.shaders import lit_with_shadows_shader, unlit_shader
from src.config import SPAWN_ALPHA, SPAWN_BETA, grid_to_world


class ChargingStation(Entity):
    def __init__(self, warehouse):
        super().__init__(parent=warehouse, name='charging_station_v19')
        self.warehouse=warehouse
        self.indicators=[]
        root=Path(__file__).resolve().parents[2]
        choices=[root/'assets/models/docking-station.obj',root/'assets/model/docking-station.obj']
        model=next((p for p in choices if p.is_file()),None)
        if model is None:
            raise FileNotFoundError('docking-station.obj not found in assets/models or assets/model')
        # Use project-relative path so Ursina resolves the accompanying MTL too.
        model=model.relative_to(root).as_posix()
        def block(pos,scale,rgb,unlit=False):
            return Entity(parent=self,model='cube',position=pos,scale=scale,
                          color=color.rgb32(*rgb),collider=None,
                          shader=unlit_shader if unlit else lit_with_shadows_shader)
        a,b=(grid_to_world(*c,0) for c in (SPAWN_ALPHA,SPAWN_BETA))
        middle=(a+b)/2
        block(middle+Vec3(0,-.016,-.22),(2.12,.03,2.1),(37,49,58))
        for idx,(p,tint) in enumerate(((a,(85,192,182)),(b,(223,163,83)))):
            # Clear 0.14-wide gap between adjacent parking bays.
            block(p+Vec3(0,.008,-.12),(.86,.014,1.65),(65,80,87))
            for dx in (-.41,.41):
                block(p+Vec3(dx,.021,.17),(.026,.012,.98),tint)
            block(p+Vec3(0,.021,.65),(.84,.012,.026),tint)
            for dx in (-.25,0,.25):
                block(p+Vec3(dx,.024,.82),(.14,.012,.10),(205,185,130))
            # Model is centered at ground level; taller tower, width under one cell.
            charger=Entity(parent=self,model=model,position=p+Vec3(0,.025,-.48),
                           scale=Vec3(.60,1.10,.78),collider=None,
                           shader=lit_with_shadows_shader)
            charger.cast_shadows=True
            # Clean display overlay avoids coplanar faces in the source OBJ.
            Entity(parent=charger,model='cube',position=(-.017,.886,-.370),
                   scale=(.46,.31,.025),color=color.rgb32(17,34,44),
                   shader=unlit_shader,collider=None)
            bars=[]
            for i in range(5):
                bars.append(Entity(parent=charger,model='cube',
                    position=(-.173+i*.078,.88,-.349),scale=(.055,.12,.012),
                    color=color.rgb32(*tint),shader=unlit_shader,collider=None))
            # Compact status lens above the actual tower, visible in overview.
            block(p+Vec3(0,1.43,-.94),(.48,.10,.10),(32,46,54))
            lamp=block(p+Vec3(0,1.43,-.878),(.35,.036,.018),tint,True)
            self.indicators.append((lamp,tint,bars))
            # Painted stopping bars; no added collider or navigation obstacles.
            block(p+Vec3(0,.026,-.20),(.44,.012,.035),(192,205,204))
        for dx in (-1.02,1.02):
            block(middle+Vec3(dx,.18,-.91),(.10,.36,.10),(218,174,86))
            block(middle+Vec3(dx,.20,-.91),(.106,.08,.106),(37,49,58))

    def update(self):
        manager=getattr(self.warehouse,'mission_mgr',None)
        if manager is None:return
        for (lamp,tint,bars),robot in zip(self.indicators,(manager.robot_alpha,manager.robot_beta)):
            state=getattr(robot.state,'name','')
            battery=max(0,min(100,getattr(robot,'battery',100)))
            for i,bar in enumerate(bars):
                bar.color=color.rgb32(*(tint if battery>i*20 else (36,53,60)))
            if state=='CHARGING':
                pulse=.65+.35*math.sin(time.time()*4)**2
                lamp.color=color.rgb32(int(85*pulse),int(225*pulse),int(155*pulse))
            elif state=='DEAD':lamp.color=color.rgb32(222,84,70)
            else:lamp.color=color.rgb32(*tint)


def build_charging_station(warehouse):
    old=getattr(warehouse,'charging_station',None)
    if old is not None:destroy(old)
    warehouse.charging_station=ChargingStation(warehouse)
    return warehouse.charging_station

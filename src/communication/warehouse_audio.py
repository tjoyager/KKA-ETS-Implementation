"""Low-volume procedural SFX. Movement uses actual robot displacement."""
from pathlib import Path
from ursina import Audio, Button, Entity, Vec3, camera, color, time, window
from ursina.shaders import unlit_shader


class WarehouseAudio(Entity):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.muted = False
        self.available = True
        self.previous = {}
        self.states = {}
        self.level = 0.0
        self.cooldown = 0.0
        self.sounds = {}
        folder = Path(__file__).resolve().parents[2] / 'assets' / 'audio'
        try:
            for name in ('motor', 'pickup', 'dropoff'):
                self.sounds[name] = Audio(folder / ('warehouse_'+name+'.wav'),
                    autoplay=False, loop=name=='motor', volume=0 if name=='motor' else .25,
                    auto_destroy=False)
        except Exception as exc:
            self.available = False
            for sound in self.sounds.values(): sound.stop(destroy=False)
            print('[Warehouse audio] Audio unavailable:', exc)
        self.button = Button(parent=camera.ui, text='Sound ON [F8]',
            scale=(.16,.03), color=color.rgb32(31,51,59),
            text_color=color.rgb32(155,207,200), text_size=.55,
            shader=unlit_shader, on_click=self.toggle,
            font='assets/fonts/Roboto-Regular.ttf')
        if not self.available: self.button.text='Sound unavailable'

    def toggle(self):
        if not self.available: return
        self.muted = not self.muted
        self.button.text = 'Sound OFF [F8]' if self.muted else 'Sound ON [F8]'
        if self.muted:
            self.level=0
            for sound in self.sounds.values(): sound.stop(destroy=False)

    def input(self, key):
        if key == 'f8': self.toggle()

    def update(self):
        self.button.position=Vec3(window.aspect_ratio/2-.105,-.389,.005)
        dt=max(0.00001,min(float(time.dt),.1))
        self.cooldown=max(0,self.cooldown-dt)
        paused=bool(getattr(self.manager,'is_paused',False))
        moving=False
        event=None
        for robot in (self.manager.robot_alpha,self.manager.robot_beta):
            key=id(robot)
            pos=Vec3(robot.visual_body.world_position)
            prev=self.previous.get(key,pos)
            distance=(pos-prev).length()
            state=getattr(robot.state,'name','')
            active=state in ('MOVING_TO_PICKUP','MOVING_TO_DROPOFF','RETURNING_TO_DOCK')
            moving |= active and .0001 < distance < max(2,dt*35) and not robot.is_paused
            if key in self.states and self.states[key]!=state:
                if state=='LOADING_CARGO': event='pickup'
                elif state=='UNLOADING_CARGO': event='dropoff'
            self.previous[key]=pos
            self.states[key]=state
        if not self.available: return
        if paused or self.muted:
            self.level=0
            for sound in self.sounds.values(): sound.stop(destroy=False)
            return
        target=.18 if moving else 0
        self.level += (target-self.level)*min(1,dt*10)
        motor=self.sounds['motor']
        motor.volume=self.level
        if self.level>.002:
            if not motor.playing: motor.play()
        else:
            motor.stop(destroy=False)
        if event and self.cooldown==0:
            self.sounds[event].play()
            self.cooldown=.2

    def on_destroy(self):
        from ursina import destroy
        for sound in self.sounds.values(): sound.stop(destroy=False)
        for sound in self.sounds.values(): destroy(sound)
        destroy(self.button)

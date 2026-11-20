"""Engine-managed SFX with audible levels, test playback and output diagnostics."""
from pathlib import Path
from panda3d.core import Filename, AudioSound
from ursina import Entity, Button, Vec3, application, camera, color, time, window, destroy
from ursina.shaders import unlit_shader


class WarehouseAudio(Entity):
    def __init__(self,manager):
        super().__init__()
        self.manager=manager
        self.muted=False
        self.volume=.70
        self.available=False
        self.previous={}
        self.states={}
        self.level=0.
        self.cooldown=0.
        self.sounds={}
        self.error=''
        self.button=Button(parent=camera.ui,text='Sound 70% [F8]',scale=(.18,.03),
            color=color.rgb32(31,51,59),text_color=color.rgb32(155,207,200),
            text_size=.53,shader=unlit_shader,on_click=self.toggle,
            font='assets/fonts/Roboto-Regular.ttf')
        self.test_button=Button(parent=camera.ui,text='Test sound [F9]',scale=(.18,.028),
            color=color.rgb32(41,64,72),text_color=color.rgb32(220,231,227),
            text_size=.51,shader=unlit_shader,on_click=self.test_sound,
            font='assets/fonts/Roboto-Regular.ttf')
        self._load()

    def _load(self):
        self.available=False
        try:
            base=application.base
            managers=base.sfxManagerList
            if not managers or not managers[0].isValid():
                raise RuntimeError('No working audio output. Check Windows output device and Volume Mixer, then restart.')
            folder=Path(__file__).resolve().parents[2]/'assets/audio'
            for name in ('motor','pickup','dropoff'):
                path=folder/('warehouse_'+name+'.wav')
                if not path.is_file():raise FileNotFoundError(path)
                # Use ShowBase's audio manager, which is updated by the engine.
                clip=base.loader.loadSfx(Filename.fromOsSpecific(str(path)))
                if clip is None or clip.status()==AudioSound.BAD or clip.length()<=0:
                    raise RuntimeError('Cannot decode audio: '+path.name)
                clip.setLoop(name=='motor')
                clip.setVolume(0 if name=='motor' else self.volume)
                self.sounds[name]=clip
            self.available=True
            self.error=''
        except Exception as exc:
            self.error=str(exc)
            for clip in self.sounds.values():clip.stop()
            print('[Warehouse audio]',self.error)
        self._label()

    def _label(self):
        self.button.text=('Audio unavailable' if not self.available else
                          ('Sound OFF [F8]' if self.muted else f'Sound {int(self.volume*100)}% [F8]'))

    def toggle(self):
        if not self.available:self._load();return
        self.muted=not self.muted
        if self.muted:self._stop()
        self._label()

    def _stop(self):
        self.level=0
        for clip in self.sounds.values():clip.stop()

    def test_sound(self):
        if not self.available:self._load()
        if not self.available:return
        self.muted=False
        self._label()
        clip=self.sounds['pickup'];clip.setVolume(self.volume);clip.play()
        print('[Warehouse audio] Playing test tone at',int(self.volume*100),'percent')

    def input(self,key):
        if key=='f8':self.toggle()
        elif key=='f9':self.test_sound()
        elif key in ('f6','f7'):
            self.volume=round(max(.1,min(1,self.volume+(.1 if key=='f7' else -.1))),2)
            self._label()

    def update(self):
        self.button.position=Vec3(window.aspect_ratio/2-.115,-.389,.005)
        self.test_button.position=Vec3(window.aspect_ratio/2-.115,-.354,.005)
        dt=max(.00001,min(float(time.dt),.1))
        self.cooldown=max(0,self.cooldown-dt)
        paused=bool(getattr(self.manager,'is_paused',False))
        moving=False;event=None
        for robot in (self.manager.robot_alpha,self.manager.robot_beta):
            key=id(robot)
            # Track logical translation, not visual offsets or animated accessories.
            pos=Vec3(robot.world_position)
            previous=self.previous.get(key,pos)
            delta=(pos-previous).length()
            state=getattr(robot.state,'name','')
            active=state in ('MOVING_TO_PICKUP','MOVING_TO_DROPOFF','RETURNING_TO_DOCK')
            moving |= active and .00001<delta<max(2,dt*35) and not robot.is_paused
            if key in self.states and self.states[key]!=state:
                if state=='LOADING_CARGO':event='pickup'
                elif state=='UNLOADING_CARGO':event='dropoff'
            self.previous[key]=pos;self.states[key]=state
        if not self.available:return
        if self.muted:
            self._stop();return
        motor=self.sounds['motor']
        # Paused simulation silences movement; explicit Test sound still works.
        if paused:
            self.level=0;motor.stop();return
        target=self.volume*.65 if moving else 0.
        self.level+=(target-self.level)*min(1,dt*12)
        motor.setVolume(self.level)
        if self.level>.003:
            if motor.status()!=AudioSound.PLAYING:motor.play()
        else:motor.stop()
        if event and self.cooldown==0:
            clip=self.sounds[event];clip.setVolume(self.volume);clip.play();self.cooldown=.2

    def on_destroy(self):
        self._stop()
        destroy(self.button);destroy(self.test_button)

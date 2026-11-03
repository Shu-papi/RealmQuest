# Kendi sprites (pygame)

```
main.py              playable demo
kendi_sprites.py     animation loader + Kendi state machine (idle/walk/run/attack)
assets/sprites/kendi/{idle,walk,run,attack}/<name>_NN.png
tests/test_kendi.py
requirements.txt
```

## Run
```
pip install -r requirements.txt
python main.py
```
Controls: A/D or arrows = move, Shift = run, Space/J = attack, Esc = quit.

## Use in your own game
```python
from kendi_sprites import Kendi
kendi = Kendi(x=400, y=450, scale=1.0)   # (x, y) = feet
kendi.handle_input(pygame.key.get_pressed())   # or kendi.set_input(dir, run)
kendi.update(dt)                               # dt in seconds
kendi.draw(screen)
kendi.attack()
kendi.on_attack_hit = lambda frame: ...        # fires on attack frames 10-12
```
Tune fps / anchors / HIT_FRAMES at the top of `kendi_sprites.py`.

## Test
```
pip install pytest
python -m pytest tests
```

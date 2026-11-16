"""Generated scenes keep regression coverage independent of private captures."""
import unittest
from PIL import Image, ImageDraw
from blockblast.vision import read


def scene(background, block, strip=False):
    image=Image.new('RGB',(640,1040),background)
    draw=ImageDraw.Draw(image)
    for row in range(8):
        for col in range(8):
            x,y=48+col*68,100+row*68
            draw.rectangle((x,y,x+67,y+67),fill=(30,25,20))
            draw.rectangle((x+4,y+4,x+63,y+63),fill=(100,65,35))
    if strip:
        draw.rectangle((565,700,591,919),fill=tuple(min(255,c+40) for c in background))
    shapes={0:((0,1),(0,2),(1,0),(1,1)),1:tuple((r,0) for r in range(5))}
    for slot,shape in shapes.items():
        for row,col in shape:
            x,y=80+slot*182+col*30,730+row*30
            draw.rectangle((x,y,x+28,y+28),fill=block)
            draw.line((x,y,x+28,y),fill=tuple(min(255,c+25) for c in block),width=3)
            draw.line((x,y+28,x+28,y+28),fill=tuple(max(0,c-25) for c in block),width=3)
    return image,shapes


class GeneratedVisionTests(unittest.TestCase):
    def test_empty_slot_lighting_is_not_a_piece_and_five_cell_line_survives(self):
        for bg,block in [((170,120,75),(80,70,200)),((65,65,65),(160,160,160)),
                         ((90,45,65),(220,130,170)),((130,130,130),(155,155,155)),
                         ((180,100,130),(210,140,170))]:
            image,expected=scene(bg,block,True)
            for scale in (1,.5):
                with self.subTest(background=bg,scale=scale):
                    frame=image.resize((round(640*scale),round(1040*scale)),Image.Resampling.BILINEAR)
                    frame.info['capture_scale']=scale
                    result=read(frame,{'screen_size':[640,1040],'board':[48,100,592,644],
                                       'tray':[48,700,592,920],'tray_cell':30})
                    self.assertEqual({i:p.shape for i,p in result.pieces.items()},expected)

    def test_generated_board_can_be_found_without_phone_calibration(self):
        image,_=scene((170,120,75),(80,70,200))
        for scale in (1,.5):
            frame=image.resize((round(640*scale),round(1040*scale)),Image.Resampling.BILINEAR)
            frame.info['capture_scale']=scale
            state=read(frame)
            for found,expected in zip(state.bounds,(48,100,592,644)):
                self.assertAlmostEqual(found,expected,delta=4)

    def test_moving_outline_does_not_move_the_cube_anchor(self):
        from blockblast.stability import StableState
        from blockblast.vision import State,Piece
        consensus=StableState(3,.2)
        shape=tuple((r,0) for r in range(5))
        for i,delta in enumerate((0,4,-3,2)):
            piece=Piece(shape,(125,125),(100,100,150,350+delta))
            ready=consensus.observe(State(0,{0:piece},(0,0,800,800),(1000,1600)),i*.1)
        self.assertTrue(ready)

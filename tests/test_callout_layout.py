import unittest
from logioptions.callout_layout import layout_callouts,diagram_geometry


class CalloutLayoutTests(unittest.TestCase):
    def test_long_labels_stay_separate_and_each_line_reaches_its_target(self):
        items=[dict(key=i,side=side,anchor=anchor,width=220 if i==0 else 160,height=70)
               for i,(side,anchor) in enumerate([('left',(.4,.36)),('left',(.43,.47)),
                 ('left',(.31,.49)),('left',(.48,.60)),('right',(.75,.19)),
                 ('right',(.80,.40)),('right',(.60,.51))])]
        for width,height in [(620,480),(900,650),(1100,700)]:
            with self.subTest(width=width,height=height):
                x,y,w,h=diagram_geometry(items,width,height)
                positions=layout_callouts(items,x,y,w,h,width,height)
                for item in items:
                    box=positions[item['key']]
                    self.assertGreaterEqual(box['x'],0)
                    self.assertGreaterEqual(box['y'],0)
                    self.assertLessEqual(box['x']+box['width'],width)
                    self.assertLessEqual(box['y']+box['height'],height)
                    self.assertEqual(box['points'][0],(x+item['anchor'][0]*w,y+item['anchor'][1]*h))
                boxes=list(positions.values())
                for i,a in enumerate(boxes):
                    for b in boxes[i+1:]:
                        self.assertTrue(a['x']+a['width']<=b['x'] or b['x']+b['width']<=a['x'] or
                                        a['y']+a['height']<=b['y'] or b['y']+b['height']<=a['y'])

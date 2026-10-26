"""Place button labels in two lanes and connect each to its physical target."""


def layout_callouts(items, image_x, image_y, image_width, image_height, width, height):
    result = {}
    for side in ('left','right'):
        group = sorted((item for item in items if item['side']==side),key=lambda item:item['anchor'][1])
        if not group: continue
        available=max(1,height-16)
        gap=min(14,max(4,(available-sum(item['height'] for item in group))/max(1,len(group)-1)))
        desired=[image_y+item['anchor'][1]*image_height-item['height']/2 for item in group]
        positions=[]
        for index,(item,y) in enumerate(zip(group,desired)):
            positions.append(max(y,positions[-1]+group[index-1]['height']+gap) if index else y)
        shift=sum(a-b for a,b in zip(desired,positions))/len(group)
        shift=max(shift,8-positions[0])
        shift=min(shift,height-8-positions[-1]-group[-1]['height'])
        for index,(item,y) in enumerate(zip(group,positions)):
            y=max(8,y+shift)
            box_width=item['width']
            scale=image_width/308
            x=image_x+32*scale-box_width if side=='left' else image_x+image_width+18*scale
            x=max(8,min(x,width-box_width-8))
            anchor=(image_x+item['anchor'][0]*image_width,image_y+item['anchor'][1]*image_height)
            edge=x+box_width if side=='left' else x
            center=y+item['height']/2
            # Separate elbow lanes prevent shared line segments between targets.
            elbow=edge+(12+index*12)*(1 if side=='left' else -1)
            elbow=min(elbow,anchor[0]-8) if side=='left' else max(elbow,anchor[0]+8)
            result[item['key']]={'x':x,'y':y,'width':box_width,'height':item['height'],
                'points':[anchor,(elbow,anchor[1]),(elbow,center),(edge,center)]}
    return result


def diagram_geometry(items,width,height):
    left_width=max((item['width'] for item in items if item['side']=='left'),default=0)
    right_width=max((item['width'] for item in items if item['side']=='right'),default=0)
    scale=max(.4,min(1,(width-left_width-right_width-32)/294,(height-24)/480))
    image_width,image_height=308*scale,480*scale
    left=(width-image_width-50*scale-right_width+left_width)/2
    top=max(12,(height-image_height)/2)
    return left,top,image_width,image_height

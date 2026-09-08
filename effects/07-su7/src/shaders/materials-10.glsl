#include <dithering_fragment>
            float discardLightMask = (1.-step(mm,(1. - vDiscardOpacity)))*step(mm,(1. - vDiscardOpacity)+0.002);
            gl_FragColor = vec4(vec3(mix(gl_FragColor.rgb,vec3(0.5,0.9,1.),vec3(discardLightMask))),gl_FragColor.a);

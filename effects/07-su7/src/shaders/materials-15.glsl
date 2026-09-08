varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    varying vec3 vPositionW;
    varying vec3 vNormalW;

    uniform vec3 uColor;
    uniform float time;
    uniform float opacity;
    uniform vec3 uCenter1;
    uniform vec3 uCenter2;

    const float X_By_Y = 2.3; //  x/z椭圆长宽比

    //椭圆化
    float normalizedEllipticalDistance(vec3 position, vec3 center, float radius) {
        vec2 d = center.xz - position.xz;
        d.y *= X_By_Y;
        return length(d) / radius;
    }

    void main() {

        float distanceP = clamp(1. - normalizedEllipticalDistance(vPositionW, uCenter1, 4.3), 0., 1.);
        distanceP += clamp(1. - normalizedEllipticalDistance(vPositionW, uCenter2, 4.3), 0., 1.);

        float uv_x = vUv.x*10. - time*3.;
        float maskCos = cos(uv_x);

        float maskX = mod(vUv.x*10.-time*3.,1.);
        maskX = step(maskX,0.2+distanceP*0.8);
        maskX *= maskCos;

        float maskY = mod(vUv.y*100.,1.);
        maskY = step(maskY,0.2);

        float mask = maskX*maskY;

        vec3 color = mix(uColor,vec3(0.1,1.,0.2),vec3(smoothstep(0.,0.5,distanceP)));
        
        gl_FragColor = vec4(vec3(color),clamp(mask*opacity,0.,1.));
        // gl_FragColor = vec4(vec3(distanceP),1.);
    }

float random (vec2 st) {
    return fract(sin(dot(st.xy,
                         vec2(12.9898,78.233)))*
        43758.5453123);
}

vec3 pos2col ( vec2 ipos ) {

    ipos += vec2(9.,0.); // Just moved to pick some nice colors
    
    float r = random( ipos + vec2( 12., 2. ) );
    float g = random( ipos + vec2(7., 5. ) );
    float b = random( ipos );

    
    vec3 col = vec3(r,g,b);
    return col;
}

vec3 colorNoise ( vec2 st ) {
    vec2 ipos = floor( st );
    vec2 fpos = fract( st );

    
    // Four corners in 2D of a tile
    vec3 a = pos2col(ipos);
    vec3 b = pos2col(ipos + vec2(1.0, 0.0));
    vec3 c = pos2col(ipos + vec2(0.0, 1.0));
    vec3 d = pos2col(ipos + vec2(1.0, 1.0));
    
    // Cubic Hermine Curve.  Same as SmoothStep()
    vec2 u = fpos*fpos*(3.0-2.0*fpos);
    // u = smoothstep(0.,1.,fpos);
    
    // Mix 4 coorners percentages
    return mix(a, b, u.x) +
            (c - a)* u.y * (1.0 - u.x) +
            (d - b) * u.x * u.y;
}

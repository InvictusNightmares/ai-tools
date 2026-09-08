varying vec4 vWorldPosition;
    varying vec2 vUv;
    varying vec2 vUv2;
    varying vec4 vViewPosition;
    varying vec3 vNormal;
    varying vec4 vTangent;

    uniform vec3 color;
    uniform sampler2D map;
    uniform float opacity;
    uniform float roughness;
    uniform sampler2D roughnessMap;
    uniform float metalness;
    uniform sampler2D metalnessMap;
    uniform sampler2D aoMap;
    uniform sampler2D lightMap;
    uniform vec3 lightMapColor;
    uniform float lightMapIntensity;
    uniform vec3 emissive;
    uniform sampler2D emissiveMap;
    uniform sampler2D normalMap;
    uniform float distortionScale;
    uniform float u_floor_typeSwitch;
    uniform sampler2D ut_street;

    uniform float u_lightIntensity;
    uniform float u_reflectIntensity;
    uniform vec2 u_floorUVOffset;

    uniform mat4 u_reflectMatrix;
    uniform sampler2D u_reflectTexture;

    #include <common>
    #include <packing>
    #include <bsdfs>
    #include <fog_pars_fragment>
    #include <logdepthbuf_pars_fragment>
    #include <lights_pars_begin>
    #include <shadowmap_pars_fragment>
    #include <shadowmask_pars_fragment>

    vec4 getNoise( vec2 uv ) {
        vec2 uv0 = ( uv / 103.0 );
        vec2 uv1 = uv / 107.0;
        vec2 uv2 = uv / vec2( 8907.0, 9803.0 );
        vec2 uv3 = uv / vec2( 1091.0, 1027.0 );
        vec4 noise = texture2D( normalMap, uv0 ) +
            texture2D( normalMap, uv1 ) +
            texture2D( normalMap, uv2 ) +
            texture2D( normalMap, uv3 );
        return noise * 0.5 - 1.0;
    }

    void main(){
        #include <logdepthbuf_fragment>

        vec3 surfaceNormal = vec3(0.,1.,0.);
        #ifdef USE_NORMAL_MAP
            vec3 normalSample = texture2D( normalMap, vWorldPosition.xz+u_floorUVOffset).rgb*2.-vec3(1.);
            surfaceNormal = normalize( normalSample.xzy );
        #endif

        vec3 diffuseLight = vec3(0.0);
        vec3 eyeDirection = -vViewPosition.xyz;
        float d = length(eyeDirection);
        eyeDirection = normalize(eyeDirection);

        //法线对反射的影响强度
        vec2 distortion = surfaceNormal.xz * ( 0.001 + 1.0 / d ) * distortionScale;

        float metallic = metalness;
        #ifdef USE_METALNESS_MAP
            metallic = texture2D(metalnessMap, vUv).b * metallic;
        #endif

        float theta = max( dot( eyeDirection, vNormal ), 0.0 );
        float rf0 = 0.02;
        float reflectance = rf0 + ( 1.0 - rf0 ) * pow( ( 1.0 - theta ), 2.0 );

        float roughness_factory = roughness;
        #ifdef USE_ROUGHNESS_MAP
            roughness_factory *= texture2D(roughnessMap, (vWorldPosition.xz+u_floorUVOffset)*0.2).g;
        #endif
        roughness_factory = roughness_factory*(1.7 - 0.7*roughness_factory);

        vec4 samplePoint = u_reflectMatrix * vWorldPosition;
        samplePoint = samplePoint / samplePoint.w;
        vec3 reflectionSample = texture2D(u_reflectTexture, samplePoint.xy + distortion, roughness_factory*6.).xyz * u_reflectIntensity;
        vec3 lightSample = vec3(lightMapIntensity * u_lightIntensity)*lightMapColor;

		#ifdef USE_LIGHT_MAP
			lightSample *= texture2D(lightMap,vUv2).rgb;
		#endif

        #ifdef USE_AO_MAP
			float aoSample = texture2D(aoMap,vUv2).r;
			lightSample*=aoSample;
		#endif

        vec3 streetCol = texture(ut_street,vec2((vWorldPosition.z+15.)/30.,(vWorldPosition.x+u_floorUVOffset.x)/60.)).rgb;
        lightSample = mix(lightSample,streetCol,vec3(u_floor_typeSwitch));

        vec3 colorFactory = color;
        #ifdef USE_MAP
            vec3 mapColor =  texture2D(map, vUv).rgb;
            mapColor = mix(mapColor,vec3(1.),vec3(u_floor_typeSwitch));
            colorFactory *= mapColor.rgb;
        #endif

        //漫反射强度的简单计算方式
        diffuseLight = lightSample * colorFactory; //* theta;
        vec3 outColor = mix(diffuseLight, reflectionSample, reflectance);

        gl_FragColor = vec4(outColor, opacity);
        // gl_FragColor = vec4(vec3(theta*(roughness_factory)), 1.);
        // gl_FragColor = vec4(vec3(vUv,0.), 1.);
        #include <tonemapping_fragment>
        #include <encodings_fragment>
        #include <fog_fragment>
    }

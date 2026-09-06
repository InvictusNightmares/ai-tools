base_color = vec3(0);
base_color = combineColor();
base_color += getEmission();
base_color = addFog(base_color);



if(enable_cc){
    custom_specular_color = vec3(0);
    c_dDiffuseLight = vec3(0);
    c_dSpecularLight = vec3(0);
    c_dReflection = vec4(0);
    c_dSpecularity = vec3(0);


    if(enable_albedo){
        getAlbedo_c();
    }
    getSpecularity_c();
    getGlossiness_c();
    getFresnel_c();
    addReflection_c();

    coat_color = combineColor_c2();


    coat_color *= dAo;
    c_dAo = dAo;


    if(show_mode == 100 || show_mode == 102 || show_mode == 103){
        mix_color = base_color+ coat_color * coat_weight_base;
        if(show_mode == 100){
            float fresnel = 1.0 - max(dot(vNormalW, dViewDirW), 0.5);
            float fresnel2 = fresnel * fresnel;
            mix_color += fresnel2 * vec3(0.15,0.0,0.15) * 0.3;
        }
        
    }
    if(show_mode == 101){
        mix_color = mix(base_color, coat_color, dSpecularity)   *reflection_reflectivity *dAo ;
        mix_color += coat_color * coat_weight_base;
    }




    gl_FragColor.rgb = mix_color ;

}
else{
    gl_FragColor.rgb = base_color;
}


#ifndef HDR
gl_FragColor.rgb = toneMap(gl_FragColor.rgb);
gl_FragColor.rgb = gammaCorrectOutput(gl_FragColor.rgb);
#endif

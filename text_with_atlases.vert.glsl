#ifdef GL_ES
precision mediump float;
#endif

attribute vec2 a_position_0;
attribute vec4 a_color_0;
attribute vec3 a_texcoord_0;

uniform mat3 iMvpInverse;
uniform mat3 iMvp;

// Shadow control
// Флаг тени. bool + if оптимален т.к. все фрагменты идут по одной ветке
// (coherent branching)
uniform float isShadow;

uniform mat3 shadowTransform; // offset, scale, pivot
uniform vec4 overridedColor;

varying vec3 texCoord;
varying vec4 vertexColor;

#define EPSILON 1e-6

void main()
{
    vec2 finalPos;
    vec4 finalColor;

    if (isShadow > EPSILON)
    {
        vec2 lPos = vec2(iMvpInverse * vec3(a_position_0, 1.0));
        lPos = (shadowTransform * vec3(lPos, 1.0)).xy;
        
        finalPos = (iMvp * vec3(lPos, 1.0)).xy;
        finalColor = overridedColor;
    }
    else
    {
        // Простой код без тени
        finalPos = a_position_0;
        finalColor = a_color_0;
    }

    texCoord = a_texcoord_0;
    vertexColor = finalColor;
    gl_Position = vec4(finalPos, 0.0, 1.0);
}
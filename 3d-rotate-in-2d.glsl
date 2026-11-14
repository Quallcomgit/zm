#ifdef GL_ES
precision mediump float;
#endif

uniform mat3 iMvp;
uniform mat3 iMvpInverse;

uniform mat4 model;

attribute vec2 a_position_0;
attribute vec4 a_color_0;
attribute vec2 a_texcoord_0;

varying vec2 texCoord;
varying vec4 vertexColor;

mat4 convertToMatrix4(mat3 m3)
{
    mat4 m4;
    m4[0] = vec4(m3[0], 0.0);
    m4[1] = vec4(m3[1], 0.0);
    m4[2] = vec4(m3[2], 0.0);
    m4[3] = vec4(0.0, 0.0, 0.0, 1.0);
    return m4;
}

void main()
{
    vec4 position = vec4(a_position_0, 1.0, 1.0);
    position.xyz = iMvpInverse * position.xyz;
    position = position * model;

    // z координата выставляется в единицу, потому что стандартная MVP матрица
    // является матрицей для трансформации 2D объектов
    // В ином случае будет некорректная трансформация
    position.z = 1.0;

    texCoord = a_texcoord_0;
    vertexColor = a_color_0;
    gl_Position = convertToMatrix4(iMvp) * position;
}
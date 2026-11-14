#ifdef GL_ES
precision highp float;
#endif

uniform mat4 matrix;

attribute vec4 POSITION_UV_2;
attribute vec4 COLOR_0;

varying vec2 texCoord;
varying vec4 vertexColor;

void main()
{
    gl_Position = vec4(POSITION_UV_2.xy, 1.0, 1.0) * matrix;
    texCoord = POSITION_UV_2.zw;
    vertexColor = COLOR_0;
}
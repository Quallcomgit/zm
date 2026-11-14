#ifdef GL_ES
precision mediump float;
#endif

attribute vec2 a_position_0;
attribute vec4 a_color_0;
attribute vec2 a_texcoord_0;

varying vec2 texCoord;
varying vec4 vertexColor;

void main()
{
    texCoord.xy = a_texcoord_0.xy;
    vertexColor = a_color_0;
    gl_Position = vec4(a_position_0, 0.0, 1.0);
}

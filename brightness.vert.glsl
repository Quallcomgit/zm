#ifdef GL_ES
precision mediump float;
#endif

attribute vec2 a_position_0;
attribute vec4 a_color_0;
attribute vec2 a_texcoord_0;

uniform float brightness;
uniform vec4 matteColor;

varying vec2 texCoord;
varying vec4 vertexColor;

void main()
{
    texCoord.xy = a_texcoord_0.xy;

    vec4 c = a_color_0 * matteColor;
    vertexColor = vec4(c.r * brightness, c.g * brightness, c.b * brightness, a_color_0.a);

    gl_Position = vec4(a_position_0, 0.0, 1.0);
}
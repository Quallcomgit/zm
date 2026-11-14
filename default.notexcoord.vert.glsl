#ifdef GL_ES
precision mediump float;
#endif

attribute vec2 a_position_0;
attribute vec4 a_color_0;

varying vec4 vertexColor;

void main()
{
    vertexColor = a_color_0;
    gl_Position = vec4(a_position_0, 0.0, 1.0);
}
#ifdef GL_ES
precision highp float;
#endif

uniform mat4 matrix;

attribute vec2 POSITION_0;

void main()
{
    gl_Position = vec4(POSITION_0, 1.0, 1.0) * matrix;
}
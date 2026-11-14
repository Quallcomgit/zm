#ifdef GL_ES
precision mediump float;
#endif

attribute vec2 a_position_0;
attribute vec4 a_color_0;
attribute vec2 a_texcoord_0;

attribute vec4 a_instanced_0; // posX, posY, scaleX, scaleY
attribute vec4 a_instanced_1; // rotationSin, Cos, frame, [reserved]
attribute vec4 a_instanced_color_0; // color

uniform float isometric;
uniform float aspectRatio;

uniform vec2 pivot;
uniform vec2 flip;
uniform vec2 texCoordData;
uniform mat3 iMvp;

// поворот частицы родительского эмиттера
uniform float parentRotation;

// скейл частицы родительского эмиттера
uniform vec2 parentScale;

varying vec2 texCoord;
varying vec4 vertexColor;

void main()
{
    float frame = a_instanced_1.z;

    texCoord = vec2(texCoordData.x * frame + a_texcoord_0.x * texCoordData.y, a_texcoord_0.y);
    vertexColor = a_color_0 * a_instanced_color_0;

    vec2 pos = a_instanced_0.xy;
    vec2 scale = a_instanced_0.zw * parentScale;

    if (isometric < 0.0)
    {
        pos = vec2(pos.x + pos.y, (pos.y - pos.x) * 0.5);
    }
    vec2 size = vec2(scale.x * flip.x, scale.y * aspectRatio * flip.y);

    vec2 local = (a_position_0 - pivot) * size;

    float sinR = sin(a_instanced_1.x + parentRotation);
    float cosR = cos(a_instanced_1.x + parentRotation);
    vec2 rotated = vec2(
        cosR * local.x - sinR * local.y,
        sinR * local.x + cosR * local.y
    );
    pos += rotated;
    gl_Position = vec4(vec2(iMvp * vec3(pos, 1.0)), 0.0, 1.0);
}
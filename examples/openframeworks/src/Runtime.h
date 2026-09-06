#pragma once

// Copyright (c) 2026 Daito Manabe. MIT; viewer code only.
// Deterministic capture acceptance checks, independent of any BVH addon.
#include "ofMain.h"
#include "ofAppGLFWWindow.h"
#include <GLFW/glfw3.h>

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace g1 {

struct RunOptions {
	bool smokeTest = false;
	int frames = 180;
	std::string capturePath;
};

class Runtime {
public:
	explicit Runtime(const RunOptions& options) : options(options) {}

	void setup() const {
		ofSetFrameRate(options.smokeTest ? 0 : 60);
		ofSetVerticalSync(!options.smokeTest);
		if (options.smokeTest) ofSetRandomSeed(2012);
	}

	float deltaSeconds() const { return options.smokeTest ? 1.0f / 60.0f : ofGetLastFrameTime(); }
	float elapsedSeconds() const { return options.smokeTest ? ofGetFrameNum() / 60.0f : ofGetElapsedTimef(); }
	bool isSmokeTest() const { return options.smokeTest; }

	void finishFrame(bool ready, const std::string& name, size_t geometryVertices) const {
		if (!options.smokeTest) return;
		auto* window = dynamic_cast<ofAppGLFWWindow*>(ofGetWindowPtr());
		auto* nativeWindow = window ? window->getGLFWWindow() : nullptr;
		const bool passive = nativeWindow && !glfwGetWindowAttrib(nativeWindow, GLFW_VISIBLE)
			&& !glfwGetWindowAttrib(nativeWindow, GLFW_FOCUSED);
		const GLenum error = glGetError();
		if (!ready || !passive || error != GL_NO_ERROR) {
			ofLogError(name) << "SMOKE_TEST_FAILED ready=" << ready << " passive=" << passive << " glError=" << error;
			ofExit(1);
			return;
		}
		const bool lastFrame = ofGetFrameNum() + 1 >= options.frames;
		if (ofGetFrameNum() != 0 && !lastFrame) return;

		ofImage capture;
		capture.grabScreen(0, 0, ofGetWidth(), ofGetHeight());
		const auto& pixels = capture.getPixels();
		if (!pixels.isAllocated() || pixels.getWidth() < 16 || pixels.getHeight() < 128) {
			ofLogError(name) << "SMOKE_TEST_FAILED framebuffer capture unavailable";
			ofExit(1);
			return;
		}
		unsigned char minimum = 255;
		unsigned char maximum = 0;
		uint64_t hash = 1469598103934665603ull;
		size_t variedPixels = 0;
		const int left = pixels.getWidth() / 10;
		const int right = pixels.getWidth() * 9 / 10;
		const int top = std::max(100, int(pixels.getHeight() / 10));
		const int bottom = pixels.getHeight() * 9 / 10;
		const auto reference = pixels.getColor(left, top);
		for (int y = top; y < bottom; ++y) {
			for (int x = left; x < right; ++x) {
				const auto color = pixels.getColor(x, y);
				for (const auto channel : {color.r, color.g, color.b}) {
					minimum = std::min(minimum, channel);
					maximum = std::max(maximum, channel);
					hash = (hash ^ channel) * 1099511628211ull;
				}
				if (std::abs(int(color.r) - reference.r) + std::abs(int(color.g) - reference.g)
					+ std::abs(int(color.b) - reference.b) > 24) ++variedPixels;
			}
		}
		if (!lastFrame) {
			initialPixelsHash = hash;
			return;
		}
		if (!pixels.isAllocated() || geometryVertices == 0 || maximum - minimum < 8
			|| variedPixels < size_t((right - left) * (bottom - top)) / 500 || hash == initialPixelsHash) {
			ofLogError(name) << "SMOKE_TEST_FAILED empty, flat, or unchanged content region"
				<< " vertices=" << geometryVertices << " variedPixels=" << variedPixels;
			ofExit(1);
			return;
		}
		if (!options.capturePath.empty() && !capture.save(options.capturePath)) {
			ofLogError(name) << "SMOKE_TEST_FAILED unable to save capture";
			ofExit(1);
			return;
		}
		ofLogNotice(name) << "SMOKE_TEST_OK frames=" << options.frames
			<< " renderer=GL3 pixelRange=" << int(maximum - minimum) << " geometryVertices=" << geometryVertices
			<< " variedPixels=" << variedPixels << " motionChanged=true hidden=true focused=false";
		ofExit(0);
	}

private:
	RunOptions options;
	mutable uint64_t initialPixelsHash = 0;
};

} // namespace g1
